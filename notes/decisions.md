
# Design Decisions Log

This file records non-obvious design decisions made during the build,
along with the reasoning. Useful for résumé writing, interviews, and
future debugging.

---

## Day 1 — 2026-05-02

### D1.1 — Use mock modules before real implementations

**Decision**: Build the full pipeline (claim_extractor, retriever, verifier, agent)
with placeholder mock implementations on Day 1, then replace one module per day.

**Why**:
- Lets the end-to-end JSON schema and aggregation rules be locked in early
- Each subsequent day is a low-risk drop-in replacement, not new wiring
- Tests can be written against the schema independently of any model

**Trade-off**: Day 1 output is meaningless (random verdicts), but the architecture is exercised.

---

### D1.2 — Module-level imports in agent.py (not function-level)

**Decision**: `agent.py` imports modules (`from src import verifier`),
not functions (`from src.verifier import verify`).

**Why**: Function-level imports copy the function object into agent.py's namespace
at import time. Tests that monkey-patch `src.verifier.verify` then have no
effect because agent.py still holds a reference to the original.

**Discovered**: One unit test failed in the first run; this fixed it without
changing any business logic.

**Future benefit**: When we replace mock verifier with Mistral on Day 5,
no change to agent.py is needed — verifier.py changes internally only.

---

### D1.3 — Aggregation rule

**Decision**:
reliability_score = supported_claims / total_claims

if any claim is CONTRADICTED:
    prediction = "untrustworthy"
elif reliability_score < 0.7:
    prediction = "untrustworthy"
else:
    prediction = "trustworthy"

**Why threshold = 0.7**:
- With ~3 claims per answer (PubMedQA `long_answer` median is ~37 words, so 2-3 claims typical), 0.7 means "at least 2 of 3 claims supported"
- Lower threshold (e.g., 0.5) would let 1-out-of-2 pass too easily
- Higher (e.g., 0.9) would over-flag answers with one slightly weak claim
- This is a soft choice; revisit on Day 11 if FPR is too high or recall too low.

---

## Day 2 — In Progress



### D2.1 — Failure mode renaming: numerical_inconsistency → unsupported_numerical_claim

**Decision**: Rename and split into two sub-types tracked via metadata:
- `modified_existing_number`: rewriting an existing number in the answer
- `fabricated_percentage`: appending a number with no supporting evidence

**Why**: PubMedQA inspection showed only 21.4% of long_answers contain any number, and only 2.7% contain percentages. Pure "modify existing number" cannot fill 25 cases without dropping diversity. The new framing covers both cases under one coherent failure mode.

**Verified by**: `src/poisoner.py` sanity check, all 3 test samples produced correct subtypes.

---

### D2.2 — Skip rules to prevent absurd numerical modifications

**Decision**: When trying to modify an existing number, skip:
- Years (1900–2030)
- Small integers (< 5) — likely list/group counters
- Numbers followed by year/age/patient/condition/group context
- Numbers preceded by Figure/Table/n= context

**Why**: Without skip rules, "over the age of 70 years" → "over the age of 140 years" — absurd. Verifier could detect this via common sense rather than evidence grounding, inflating accuracy on a capability we are not actually testing.

**Verified by**: Sanity check confirmed "70 years" and "2-fold" are correctly skipped, falling back to fabrication. A safe sample ("15 percent of patients") is correctly modified to "22 percent."

---

### D2.3 — Random perturbation factor (1.5x–2.6x) instead of fixed 2x

**Decision**: When modifying an existing number, scale by a randomly chosen factor from {1.5, 1.7, 2.0, 2.3, 2.6} instead of always ×2.

**Why**: Fixed ×2 creates a learnable pattern across all modified samples. Multiplicative variation tests evidence-grounded comparison, not pattern matching.

---

### D2.4 — Diverse fabrication templates (5 templates × 8 numbers)

**Decision**: Use 5 phrasing templates × 8 candidate numbers [18, 23, 31, 37, 42, 48, 56, 63] for fabricated percentages.

**Why**: Single-template fabrication ("...by 45%") makes 13 fabricated samples pattern-identical. Diverse phrasings ("reduction in risk", "higher response rate", "lower complication rate", etc.) test the verifier's actual evidence-grounding ability. Numbers chosen are non-round to avoid statistical clichés (10%, 50%, 100%).

---

### D2.5 — All randomness goes through an explicit `rng: random.Random` parameter

**Decision**: Every poisoner function receives an `rng` object, not using global `random` state.

**Why**: Eval-set generation must be fully reproducible. Passing a `random.Random(42)` from the top-level orchestrator guarantees identical output across runs, machines, and team members.


---

### D2.6 — Disjoint pools for trustworthy and untrustworthy samples

**Decision**: Shuffle the 1000 PubMedQA examples once with seed=42, then slice into 5 disjoint chunks (100 trustworthy + 4×25 untrustworthy). The same `pubid` never appears in both pools.

**Why**: 
- A `long_answer` used as a trustworthy sample also has its evidence (the same paper's `context_passages`) appear in the global retrieval corpus.
- If the same paper were also poisoned and put in the untrustworthy pool, the retriever would return that paper's contexts at high similarity, and the verifier would essentially be checking the poisoned answer against text that originally generated the unpoisoned answer — an unfair signal that inflates detection rate.
- Disjoint pools eliminate this leakage and keep the retrieval task realistic.

**Cost**: We use 200 unique papers instead of potentially 100. Given 1000+ eligible papers in PubMedQA, this is not a constraint.

---

### D2.7 — Filter long_answers shorter than 25 words

**Decision**: Drop any PubMedQA example whose `long_answer` has fewer than 25 words before sampling.

**Why**:
- PubMedQA `long_answer` length distribution: min=8, median=37, mean=40 words. The bottom of the distribution has answers like 1-2 words ("yes", "Results varied").
- Day 3 claim extractor splits on sentence boundaries. Answers under 25 words often produce fewer than 2 claims, which:
  - Makes `reliability_score = supported / total` extremely noisy (e.g., 1/1 = 100% or 0/1 = 0%, no middle ground).
  - Triggers the "no_claims_extracted" fallback in the aggregator, which artificially flags trustworthy samples as untrustworthy.
- Filtering removes ~200 of 1000 examples but preserves a pool of ~800, more than enough for 200 sampled cases.

**Trade-off**: We bias the eval set slightly toward longer answers, which may not reflect the full distribution of real LLM outputs. But the alternative — letting 1-claim samples pollute the score distribution — is worse.



---

### D2.8 — Numerical quota is best-effort, not strict

**Decision**: Aim for 12 `modified_existing_number` + 13 `fabricated_percentage`, but accept whatever the data permits — `prefer_modify=True` may still fall back to fabrication when no safe number is available.

**Why**:
- A strict 12/13 quota would require either expanding the candidate pool (rejecting samples until 12 modifiable answers are found) or relaxing the skip rules. Both have downsides:
  - Expanding the pool costs disjointness (D2.6) or biases toward "samples with statistical numbers."
  - Relaxing skip rules reintroduces the "70 years → 140 years" problem (D2.2).
- A best-effort approach is more honest: the eval set reflects PubMedQA's true numerical-content distribution.
- Day 9 sub-type breakdown will report the actual achieved counts; sample-size differences are easy to control for in the analysis.



---

### D2.9 — Targeted recruitment for the `modified_existing_number` sub-type

**Problem observed**: Naïve sequential sampling produced only 4 modified-sub-type samples out of 25, far from the targeted 12. Most untrustworthy candidates lacked numerically-modifiable content (no number, year only, age only, list counter, etc.).

**Solution**: After allocating the three "simple" failure-mode chunks (unsupported_claim, hallucinated_citation, contradiction), the remaining candidate pool is scanned in deterministic order. The first 12 samples whose `long_answer` passes `_find_modifiable_number()` are recruited to the modified-sub-type pool; the next 13 unmatched samples become the fabricated-sub-type pool.

**Result**:
- Scanned 84 leftover candidates to find 12 with safely-modifiable numbers
- This implies ~14% of PubMedQA `long_answer` samples contain numerically modifiable content (lower than the 21.4% "any number" rate from D2.1, because year/age/small-int/context-skipped numbers don't qualify)
- Achieved precise 12/13 quota; sub-type comparison on Day 9 will be statistically meaningful

**Why this design choice matters**:
- Maintains D2.6 (disjoint trustworthy/untrustworthy pools) — recruitment only operates within the leftover untrustworthy candidates
- Maintains D2.5 (full reproducibility) — scanning is deterministic given seed=42
- The runtime disjointness assertion in `build_eval_set.py` provides a code-level guarantee that no `pubid` appears in both pools



---

### D2.10 — Skip rule for compound identifiers (post-hoc fix)

**Problem found during sanity check**: Manual inspection of 5 random poisoned samples revealed that "Interleukin-7" had been corrupted to "Interleukin-14" — a compound biological identifier where the trailing digit is part of the name, not a statistical quantity.

**Why this is a bug**: Modifying compound identifiers (IL-7, TGF-1, p53, COVID-19, type-2) produces invalid biological/medical entities, not retrieval-grounded errors. The verifier could detect such cases via prior knowledge ("IL-14 doesn't exist") rather than evidence grounding, inflating detection accuracy on a capability we are not actually testing — the same failure pattern D2.2 was designed to prevent.

**Fix**: Added a fifth skip rule to `_find_modifiable_number()`:
```python
# Skip: numbers attached to letters or hyphens (compound identifiers)
if match.start() > 0:
    prev_char = answer[match.start() - 1]
    if prev_char.isalpha() or prev_char == "-":
        continue
```

**Verified by**: 8-case sanity check covering IL-7, TGF-1, type-2, p53. The rule correctly skips compound identifiers while still recognizing legitimate statistical numbers (e.g., the "30 percent" after "p53" in `Mutations in p53 were observed in 30 percent of the tumor samples`).

**Impact on eval set**: Re-running `build_eval_set.py` with the new rule scanned 129 leftover candidates (vs 84 before) to assemble the modified pool. Final eval set contains 0 Interleukin-corrupted samples.

**Lesson**: Sanity check on real data caught a bug that purely synthetic test cases (D2.2 sanity check) missed. Always inspect generated data manually.


---

### D2.11 — Drop the `modified_existing_number` sub-type entirely

**Background**: D2.1 originally designed two numerical sub-types (modified vs fabricated) to enable comparative analysis on Day 9. D2.9 implemented targeted recruitment achieving precise 12/13 quota. D2.10 added skip rules for compound identifiers after sanity check found IL-7 → IL-14 corruption.

**Discovery**: Manual inspection of all 12 modified samples (with ground-truth diff) revealed 7/12 had semantically corrupted modifications:

- Medical classification codes (e.g., "OTA/AO 31A1-3 fractures" → "62A1-3")
- Standard time windows (e.g., "30-day mortality" → "51-day")
- Anatomical thresholds with units (e.g., "pupils larger than 6 mm" → "12 mm", "PTS ≥5°" → "≥10°")
- Standard experimental conditions (e.g., "5% CO(2) incubation" → "8% CO(2)")
- Age cutoffs (e.g., "women age 30 and older" → "age 45 and older")

**Root cause**: Medical reference values (classification codes, dosage standards, time windows, anatomical thresholds) and statistical results share surface form. PubMedQA's domain — clinical/biomedical writing — is dense with the former. No achievable heuristic skip rule can reliably distinguish them without semantic understanding.

**Quantitative justification**: Only 25/812 (3.1%) of eligible long_answers contain a `%` or `percent` token. Even narrowing to those, contextual modifications (e.g., "5% CO(2)") would still produce semantically odd outputs.

**Decision**: Drop the modified sub-type entirely. All 25 `unsupported_numerical_claim` samples now use `fabricated_percentage` (appending an unsupported statistical claim, which carries no risk of corrupting medical reference values).

**Trade-off accepted**: Loses the modified-vs-fabricated comparative analysis originally planned for Day 9. In exchange, gains: (a) clean, uncorrupted evaluation signal, (b) a more honest reflection of PubMedQA's domain characteristics, (c) an interesting research finding to report.

**Lesson**: Domain-specific data has structure that resists generic poisoning. Manual inspection with ground truth comparison is essential — synthetic sanity-check cases (D2.10) caught one bug class, but only ground-truth diffs revealed the full extent of the problem.



## Day 3 — In Progress

### D3.0 — Empty `__init__.py` files lost during GitHub web-UI upload

**Problem**: After cloning the repo on a new machine (4090 server), `python -m tests.test_pipeline` raised `No module named tests.test_pipeline`. Root cause: empty `src/__init__.py` and `tests/__init__.py` files were silently dropped during GitHub web-UI upload (which sometimes ignores zero-byte files in batch uploads).

**Fix**: Recreated both with `touch src/__init__.py tests/__init__.py`. Pipeline tests then ran 7/7 passing on the new machine, identical to the 3070 baseline.

**Lesson**: For future day-end uploads, prefer `git push` over web-UI upload. Empty marker files are a reproducibility footgun.

---

### D3.1 — Replace mock period-split with NLTK Punkt sentence tokenizer

**Decision**: Replace `answer.replace('?', '.').replace('!', '.').split('.')` (Day 1 mock) with `nltk.sent_tokenize()`.

**Why NLTK**:
- Period-based splitting fails on common medical abbreviations: `Dr.`, `Fig.`, `vs.`, `i.e.`, `e.g.`, `et al.`
- Decimal numbers and p-values: `5.7%`, `p=0.05`
- Citation references: `(Smith et al., 2018, Lancet)`
- URLs in trial registries: `ClinicalTrials.gov`
- NLTK Punkt is statistically trained on English text, handles all of these cases.

**Why not LLM-based atomic claim splitting** (deferred to potential Day 11 optimization):
- LLM-based splitting introduces cascading hallucination risk (using LLM to evaluate LLM output)
- Slower (1 LLM call per claim → much higher latency)
- Sentence-level granularity is sufficient for our verification task per the project scope (D1.1)

**Verified by**:
- 10/10 unit tests in `tests/test_claim_extractor.py` covering Dr./Fig./decimals/citations/empty input/short fragments
- 10 random eval_set samples manually inspected: all sentence boundaries respected
- Pipeline integration: `tests.test_pipeline` 7/7 passing (no regression)

**Quantitative comparison on 200 eval_set samples**:
| Metric | Mock | NLTK |
|--------|------|------|
| Total claims extracted | 532 | 524 |
| Avg claims per answer | 2.66 | 2.62 |
| Samples with disagreements | — | 8 / 200 (4%) |

**Aggregate parity hides quality difference**: aggregate counts look similar because mock's mistakes cancel out (1 sentence → 2 fragments adds 1, then short fragments get filtered subtracting 1). Sample-level inspection (e.g., id=50) reveals mock breaks `insulin glargine vs. standard care` into `["...vs", "standard care..."]` and breaks `ClinicalTrials.gov` URLs at the `.gov`. NLTK preserves both.

**Lesson**: Aggregate metrics are insufficient for evaluating preprocessing quality. Sample-level diff is essential.




## Day 4 — In Progress

### D4.1 — Replace mock retriever with FAISS + sentence-transformers (all-MiniLM-L6-v2)

**Decision**: Replace the Day 1 mock retriever with FAISS over PubMedQA contexts, embedded via `all-MiniLM-L6-v2`.

**Why this model**:
- 22MB, encodes 3347 passages in 1 second on RTX 4090 (vs 30-60s estimated)
- Strong generic baseline; medical-domain models (e.g., S-PubMedBert) deferred to Day 11 optimization
- Cosine similarity via L2-normalized embeddings + IndexFlatIP

**Why disk-cached index**:
- First build takes ~5s (embedding + FAISS); cached load < 2s
- Day 5-12 will iterate the verifier dozens of times; rebuilding the index every run wastes time
- Cache invalidation: delete `data/faiss.index` to force rebuild

**Architecture choice — module-level singleton**:
- `Retriever` class encapsulates state (model, index, passages)
- Module-level `retrieve(claim, top_k)` function preserves Day 1 mock interface
- Lazy initialization: model only loads on first call, not at import time
- Result: agent.py needs zero changes; tests/utility scripts can import without paying loading cost

**Verified by**:
- 6/6 unit tests in `tests/test_retriever.py` (singleton, top_k control, empty queries, medical relevance, deterministic results)
- Pipeline integration: `tests.test_pipeline` 7/7 passing (no regression)
- Manual inspection of 5 real eval_set samples (one per failure mode + trustworthy)

**Key qualitative findings from 5-sample inspection** (relevant for Day 5 verifier prompt design):

1. **NLTK + retrieval naturally isolates hallucinated citations**: When NLTK splits "(Rodriguez and Kim, 2022, Nature Medicine Letters)" as its own claim, retrieval returns completely unrelated passages (MEDLINE methodology, etc.). Day 5 verifier should easily judge these UNSUPPORTED. *This is the strongest detection signal in the system.*

2. **Contradiction templates are too generic**: Sentences like "Yet, parallel evidence suggests the relationship may actually be reversed" lack medical-domain vocabulary, so retrieval returns unrelated passages. Day 5 verifier will likely tag these UNSUPPORTED rather than CONTRADICTED. The overall prediction (untrustworthy) should still be correct because of the supported-ratio rule, but the failure_mode label may not match the original injection.

3. **Fabricated percentages retrieve passages that share the `%` token but differ in topic**: e.g., "37% higher response rate" retrieves "48% correct answers" (a literacy study). This is the trickiest case — verifier prompt on Day 5 will need to emphasize topical alignment, not just keyword overlap.

4. **Trustworthy claims that are policy / recommendation-style** (e.g., "imaging studies are mandatory before endoscopic examination") retrieve weaker top-1 evidence than fact-stating claims. Generic recommendations are inherently harder to ground.

**Configuration**:
- Embedding dim: 384
- Index: FAISS IndexFlatIP (exact search, no approximation)
- Default top_k: 3 (configurable per call)
- Cache files: `data/faiss.index`, `data/corpus_passages.npy` (gitignored)




cat >> notes/decisions.md << 'EOF'

## Day 5 — Mistral-7B Verifier (Complete)

### D5.1 — Verifier architecture

- Module-level singleton + lazy loading: amortizes 5s model load across 600+ verify() calls
- Singleton preserves Day 1 mock interface — agent.py unchanged
- Parser: regex primary → keyword scan fallback → UNSUPPORTED default
- Verified on RTX 4090 fp16: 14.5 GB, ~1.0s/sample, 100% parse success rate

### D5.2 — Prompt V1→V2: localized intervention succeeds

- V1: 9/10 golden test. Failure: C1 tagged UNSUPPORTED despite reasoning saying "contradicts the claim" — classic reasoning-label inconsistency in 7B models
- V2 fix: expanded CONTRADICTED definition + decision rule "same topic but disagrees → CONTRADICTED not UNSUPPORTED"
- V2 result: 10/10 golden test. No other case regressed.
- Lesson: localized prompt surgery works when the failure pattern is identifiable

### D5.3 — Prompt V2→V3: global rule causes systemic regression

- Motivation: trustworthy false negatives (3/6 = 50%) — model fixates on evidence [1] when [2-3] contains stronger support
- V3 added: "read ALL evidence", "if ANY passage supports → SUPPORTED"
- Result: trustworthy 50%→83% (+33pp) BUT overall 64%→43% (-21pp)
- Root cause: "if ANY passage supports" gave implicit permission to accept loose topical overlap as support. Model began reasoning: "evidence [2] discusses related topic, which aligns with claim" → SUPPORTED on fabricated citations and contradiction cases
- Decision: rolled back to V2. Deterministic generation (do_sample=False) confirmed exact reproduction.
- Lesson: prompt engineering trade-offs are non-monotonic. Global rules break localized fixes.

### D5.4 — Final evaluation results

**Golden test (10 cases)**: 10/10 (100%)

**36-sample unique-claim eval (V2 final)**:

| Category | Acc | Notes |
|---|---|---|
| trustworthy | 7/10 (70%) | Retrieval ranking sensitivity; "first report" meta-claims unverifiable |
| unsupported_claim | 4/5 (80%) | Template pool only 5 unique; 1 false positive |
| unsupported_numerical_claim | 6/10 (60%) | Variance across samples; 6/6 on one run, 6/10 on another |
| hallucinated_citation | 3/5 (60%) | Model conflates topic-aligned evidence with citation existence |
| contradiction | 2/6 (33%) | Data-level catch-22: generic templates lack medical specificity, retrieval returns unrelated evidence, UNSUPPORTED is the rational verdict |
| **Overall** | **22/36 (61%)** | |

**Key finding on contradiction**: 4/6 failures have factually correct reasoning ("evidence does not provide specific information about X") but wrong label. The error is upstream in data design — generic contradiction templates cannot retrieve topically-aligned counter-evidence. No prompt fix possible without changing the data (Day 11 optimization candidate).

**Key finding on template duplication**: eval_set has only 5 unique unsupported_claim templates and 5 hallucinated_citation templates across 25 samples each. Single semantic failure modes multiply across the test set. Full 200-sample eval in Day 8 will reflect this structural limitation.



# Day 6 — LangGraph Agent Refactor (Complete)

## Day 6 Mission

Day 6 的核心目标不是提升模型准确率，而是把前 5 天已经完成的模块：

* claim extractor
* retriever
* verifier
* aggregation

整合成一个真正可扩展、可调试、可研究的 Agent Pipeline。

Day 1–5 的重点是：

```text
Build components.
```

Day 6 的重点是：

```text
Connect components into a graph-based reasoning system.
```

最终目标：

* 用 LangGraph 替换原始顺序调用 agent
* 明确每个 pipeline stage 的输入输出
* 强制 state schema
* 保证未来能扩展 retry / branching / self-correction
* 保持 Day 1 的 audit() 接口不变
* 跑通 end-to-end smoke test

---

# Day 6 完成的内容

Day 6 最终完成了：

```text
extract_node
retrieve_node
verify_node
aggregate_node
```

四节点 LangGraph pipeline。

最终结构：

```text
extract_node
      ↓
retrieve_node
      ↓
verify_node
      ↓
aggregate_node
      ↓
END
```

这是整个项目第一次拥有：

```text
真正的 graph-based audit pipeline
```

---

# 1. 为什么要重构 Agent

## Day 1 的 Agent 是什么？

Day 1 的版本实际上是：

```python
claims = extract_claims(answer)
retrieved = retrieve(claims)
verdicts = verify(retrieved)
result = aggregate(verdicts)
```

这种写法是：

```text
plain Python sequential calls
```

它能工作。

但问题是：

---

## 问题 1 — Dataflow 不可见

调用链只是函数嵌套。

无法看到：

* 哪一步产生了什么
* state 如何变化
* 哪一步失败
* 中间输出是什么

---

## 问题 2 — 没有 schema

函数之间靠隐式约定。

例如：

```text
retriever 假设 claims 已存在
verifier 假设 evidences 已存在
aggregate 假设 verdicts 已存在
```

但没有任何机制保证这些字段存在。

---

## 问题 3 — 无法扩展

未来如果加入：

```text
low confidence → retry retrieval
```

plain Python 需要大量 if/else。

Graph 更自然。

---

# 2. LangGraph 引入

## Day 6 决策

决定：

```text
用 LangGraph StateGraph 替代 plain Python pipeline
```

原因：

* 显式 pipeline
* state schema
* 可调试
* 可扩展
* Resume value

---

## LangGraph 的核心思想

Graph = 节点 + 边。

每个节点：

```text
读 state
修改 state
返回 state
```

没有 node 直接调用其他 node。

所有通信通过 state。

---

# 3. Graph Architecture

## 最终结构

```text
extract_node → retrieve_node → verify_node → aggregate_node → END
```

---

## Node 1 — extract_node

职责：

```text
answer → claims
```

输入：

```text
answer
```

输出：

```text
claims
```

调用：

```python
extract_claims(answer)
```

---

## Node 2 — retrieve_node

职责：

```text
claim → top-k evidence
```

输入：

```text
claims
```

输出：

```text
evidences
```

格式：

```text
list[list[str]]
```

每个 claim 对应一组 evidence。

---

## Node 3 — verify_node

职责：

```text
claim + evidence → verdict
```

输入：

```text
claims
evidences
```

输出：

```text
verdicts
```

每个 verdict 包含：

```python
{
    "verdict": "SUPPORTED",
    "reasoning": "..."
}
```

---

## Node 4 — aggregate_node

职责：

```text
verdicts → final prediction
```

输出：

```text
trustworthy / untrustworthy
```

同时计算：

```text
reliability_score
failure_modes
```

---

# 4. AuditState Schema

## Day 6 新增 TypedDict

```python
class AuditState(TypedDict):
    question: str
    answer: str
    claims: list[str]
    evidences: list[list[str]]
    verdicts: list[dict]
    reliability_score: float
    prediction: str
    failure_modes: list[str]
```

---

## 为什么需要 AuditState

### 好处 1 — 明确数据结构

任何 node 都知道：

```text
state 里应该有什么字段
```

---

### 好处 2 — 防止 KeyError

每个字段在 invoke() 时初始化。

避免：

```text
node 读取不存在字段
```

---

### 好处 3 — 更容易 debug

Graph 中任何时刻都能打印：

```python
print(state)
```

看到完整 pipeline 状态。

---

# 5. Aggregation 保持 Day 1 逻辑

Day 6 没有改变 aggregation 规则。

保持 D1.3。

---

## Aggregation Rule

```python
reliability_score = supported_claims / total_claims

if any CONTRADICTED:
    prediction = "untrustworthy"
elif reliability_score < 0.7:
    prediction = "untrustworthy"
else:
    prediction = "trustworthy"
```

---

## 为什么不改 threshold

Day 6 不是优化日。

Day 6 的目标是：

```text
controlled refactor
```

不能同时：

* 改 graph
* 改 threshold

否则无法判断 accuracy 变化来源。

---

# 6. Singleton Graph Design

## 问题

每次 audit() 都 compile graph。

会浪费时间。

---

## Day 6 设计

加入：

```python
_graph = None
```

第一次调用：

```python
build_agent()
```

后续：

```python
直接复用 graph
```

---

## 为什么重要

避免：

```text
重复 graph compile
```

对于 200 条 eval_set 很重要。

---

# 7. Public API 保持兼容

Day 6 没有改变 Day 1 接口。

仍然保留：

```python
audit(question, answer)
```

原因：

后续模块依赖该接口。

例如：

```text
batch eval
streamlit app
future CLI
```

都可以直接调用。

---

# 8. Smoke Test

Day 6 完成后进行了 smoke test。

---

## 输入

Question:

```text
Does aspirin reduce heart attack risk?
```

Answer:

```text
Aspirin reduces heart attack risk in patients with cardiovascular disease.
This effect has been demonstrated in multiple randomized controlled trials.
This was first reported by researchers at MIT in 2019.
```

---

## Pipeline Behavior

### Claim 1

```text
Aspirin reduces heart attack risk...
```

Verdict:

```text
CONTRADICTED
```

---

### Claim 2

```text
multiple randomized controlled trials
```

Verdict:

```text
SUPPORTED
```

---

### Claim 3

```text
MIT in 2019
```

Verdict:

```text
UNSUPPORTED
```

---

## Aggregated Output

```text
reliability_score = 0.333
prediction = untrustworthy
```

---

## 为什么这是成功

因为：

```text
至少一个 CONTRADICTED
```

aggregation 正确判为：

```text
untrustworthy
```

---

# 9. Performance

## Day 6 性能结果

首次运行：

```text
retriever load ≈ 2s
verifier ≈ 1s per claim
```

3 claim answer：

```text
~4 seconds
```

目标：

```text
< 60 seconds/sample
```

结果：

```text
远低于目标
```

---

# 10. Completion Status

## Day 6 已完成

### Graph Pipeline

```text
extract → retrieve → verify → aggregate
```

---

### AuditState

完整 TypedDict schema。

---

### LangGraph Agent

完成 graph compile。

---

### Public API

保持：

```text
audit(question, answer)
```

---

### Smoke Test

完整通过。

---

### End-to-End Integration

所有模块成功连接。

---

# 11. Day 6 Deliverables

## Files

```text
src/agent.py
```

---

## Graph Components

```text
extract_node
retrieve_node
verify_node
aggregate_node
```

---

## Schema

```text
AuditState
```

---

## Updated Decisions

```text
D6.1
D6.2
D6.3
D6.4
```

---

# 12. Day 6 Key Decisions

## D6.1 — LangGraph StateGraph replaces plain Python

Decision:

```text
Move to graph architecture.
```

Reason:

* explicit structure
* future branching
* better debugging

---

## D6.2 — AuditState TypedDict

Decision:

```text
Typed schema for pipeline state.
```

Reason:

* prevent missing fields
* easier debugging

---

## D6.3 — Aggregation unchanged

Decision:

```text
Keep D1.3 threshold.
```

Reason:

avoid introducing multiple variables.

---

## D6.4 — Singleton graph

Decision:

```text
Compile once, reuse.
```

Reason:

performance.

---

# 13. What Was NOT Done

Deferred to future days:

```text
20-sample smoke test → Day 7
Batch evaluation → Day 8
Streamlit integration → Day 13
```

---

# 14. Day 6 Summary

Day 6 transformed the project from:

```text
sequential function calls
```

into:

```text
graph-based reasoning pipeline
```

This is the first day where the project gained:

* inspectable execution flow
* explicit state passing
* reusable graph agent
* future extensibility

Day 6 did not improve retrieval or verifier accuracy.

Instead, it created the infrastructure needed for:

* scaling evaluation
* debugging failures
* adding retry logic
* adding conditional branches
* future research experiments

By the end of Day 6:

```text
claim_extractor.py ✅
retriever.py ✅
verifier.py ✅
agent.py (LangGraph) ✅
```

All four core modules became real.

This is the first fully integrated research pipeline in the project.




# Day 7 — Smoke Test & False Positive Analysis (Complete)

## Day 7 Mission

Day 7 的目标不是增加新模块。

Day 1–6 已经完成：

* claim extractor
* retriever
* verifier
* LangGraph agent

Day 7 的任务是：

```text
第一次让完整 pipeline 在真实 eval_set 上运行。
```

这是项目第一次真正回答：

> "这个系统到底能不能工作？"

---

# Day 7 核心目标

Day 7 重点不是提升 accuracy，而是：

* 跑完整 smoke test
* 找系统级错误
* 找 false positives
* 找 pipeline 弱点
* 验证不会 crash
* 量化性能

---

## Day 7 的问题

Day 1–6 只验证：

```text
组件是否能运行
```

但没有验证：

```text
整个系统是否真的合理
```

Day 7 是第一次：

```text
extract → retrieve → verify → aggregate
```

在真实样本上完整运行。

---

# 1. Smoke Test Setup

## Sampling Strategy

从：

```text
data/eval_set.jsonl
```

抽取 20 条样本。

使用：

```text
seed = 7
```

采用 stratified sampling。

---

## Sample Distribution

| Type                        | Count |
| --------------------------- | ----- |
| trustworthy                 | 5     |
| unsupported_claim           | 4     |
| unsupported_numerical_claim | 4     |
| hallucinated_citation       | 4     |
| contradiction               | 3     |

总计：

```text
20 samples
```

---

## 为什么用 Stratified Sampling

避免：

```text
随机 sample 导致 failure mode 偏斜
```

确保：

* 每种 failure mode 都被测试
* trustworthy 有代表性
* contradiction 不会缺失

---

# 2. Smoke Test Before Bug Fix

## 初始结果

```text
Overall Accuracy: 16/20 = 80%
Recall:           1.00
FPR:              0.80
Crashes:          0
```

---

## Interpretation

### Recall = 1.00

意味着：

```text
15/15 untrustworthy 全部被抓到
```

没有漏掉任何 hallucination。

这是一个非常强的信号。

---

### FPR = 0.80

意味着：

```text
5 个 trustworthy 中有 4 个被误判
```

系统非常敏感。

---

## 核心发现

系统并不是：

```text
检不出错误
```

而是：

```text
太容易怀疑正常答案
```

---

## Day 7 第一个重要发现

系统的主要问题不是：

```text
false negative
```

而是：

```text
false positive
```

---

# 3. Root Cause Discovery

## Bug Discovery

发现：

```text
id=50
label=trustworthy
```

被错误判成：

```text
untrustworthy
```

---

## 原因

NLTK claim extractor 提取出：

```text
Trial Registration (ORIGIN ClinicalTrials.gov number NCT00069784)
```

作为 claim。

---

## 问题

这个句子其实不是 claim。

它是：

```text
metadata sentence
```

---

## Metadata Sentence 的问题

这类句子：

* 不可验证
* retrieval 找不到 evidence
* verifier 永远输出 UNSUPPORTED

结果：

```text
reliability_score 被拉低
```

导致：

```text
false positive
```

---

# 4. Day 7 Bug Fix

## 修复位置

文件：

```text
src/claim_extractor.py
```

---

## 新增过滤器

加入：

```python
_METADATA_PATTERNS
```

用于过滤 metadata sentence。

---

## 过滤内容

新增规则：

### ClinicalTrials

```text
ClinicalTrials.gov
```

---

### Trial IDs

```text
NCT\d{5,}
```

例如：

```text
NCT00069784
```

---

### ISRCTN

```text
ISRCTN\d+
```

---

### Trial Registration

```text
Trial Registration
```

---

### Bare Citation

例如：

```text
Smith et al., 2020.
```

---

## 为什么过滤这些句子

因为它们不是：

```text
factual claims
```

它们属于：

```text
metadata
bibliographic info
registry identifiers
```

---

# 5. Verification of Fix

## 新增 Unit Test

验证：

* metadata 被过滤
* 普通句子保留
* 混合句子部分保留

---

## Result After Fix

```text
Overall Accuracy: 17/20 = 85%
Recall:           1.00
FPR:              0.60
```

---

## Improvement

| Metric   | Before | After |
| -------- | ------ | ----- |
| Accuracy | 80%    | 85%   |
| Recall   | 1.00   | 1.00  |
| FPR      | 0.80   | 0.60  |

---

## Key Improvement

trustworthy accuracy：

```text
1/5 → 2/5
```

---

# 6. Remaining False Positives

修复 metadata bug 后。

仍然剩余：

```text
3 trustworthy false positives
```

---

# 7. Case Analysis

## Case 1 — id=41

问题 claim：

```text
usefulness of criteria lists in clinical setting
```

---

## Retrieval Result

retriever 返回：

```text
study methodology passages
```

---

## Verifier Behavior

verifier 判断：

```text
evidence 没有直接支持 recommendation
```

输出：

```text
UNSUPPORTED
```

---

## Why This Happens

推荐性结论句：

```text
不容易 grounding
```

因为 corpus 更偏实验事实。

---

## Case 2 — id=19

Claim：

```text
no impact on pain nor analgesics
```

---

## Retrieval

找到：

```text
limited benefit
```

---

## Verifier Interpretation

Mistral 认为：

```text
limited benefit ≠ no impact
```

于是输出：

```text
CONTRADICTED
```

---

## Reality

这是一个：

```text
boundary case
```

模型并不完全错。

---

## Case 3 — id=6

Claim：

```text
Kupffer and endothelial damage reflected by HA serum levels
```

---

## Retrieval

返回：

```text
serum-level related evidence
```

但来自不同 context。

---

## Verifier Behavior

判断：

```text
same topic but different conclusion
```

输出：

```text
CONTRADICTED
```

---

# 8. Day 7 Key Insight

Day 7 发现：

问题不在 verifier。

而在：

```text
retrieval precision
```

---

## 真实问题

retriever 找到：

```text
topically adjacent evidence
```

不是：

```text
claim-specific evidence
```

---

## Consequence

verifier 被迫判断：

```text
partial overlap
```

容易输出：

```text
CONTRADICTED
```

---

# 9. Day 7 Final Metrics

## Final Result

```text
Overall Accuracy: 85%
Recall:           1.00
FPR:              0.60
Errors:           0 crashes
Avg Latency:      3.3 sec/sample
```

---

## Interpretation

### Strength

系统能：

```text
100% 捕获 hallucinated answers
```

---

### Weakness

系统对 trustworthy 样本：

```text
仍然偏保守
```

---

# 10. Files Changed

## Updated

```text
src/claim_extractor.py
```

新增 metadata filter。

---

## New Files

```text
tests/run_smoke_test.py
data/smoke_test.jsonl
results/smoke_test_results.jsonl
```

---

# 11. Day 7 Completion Status

## Completed

### Smoke Test

```text
20 samples
```

成功。

---

### Metadata Bug Fix

成功。

---

### False Positive Root Cause Analysis

完成。

---

### Latency Validation

完成。

---

### Zero Crash

验证通过。

---

# 12. Known Limitations

进入 Day 8 时仍存在：

---

## Limitation 1

FPR 偏高：

```text
0.60
```

---

## Limitation 2

Recommendation / conclusion sentence 难 grounding。

---

## Limitation 3

2-claim answer 对 threshold 很敏感。

例如：

```text
1 unsupported / 2 claims
→ reliability_score = 0.5
→ untrustworthy
```

---

## Limitation 4

retriever 更偏 topic similarity。

不是 strict factual alignment。

---

# 13. Day 7 Decisions

## D7.1 — Smoke test as system validation

Decision:

```text
Use 20-sample stratified evaluation.
```

Reason:

small enough to inspect manually.

---

## D7.2 — Metadata sentence filtering

Decision:

```text
Filter registry/citation metadata.
```

Reason:

prevent false positives.

---

## D7.3 — Accept remaining trustworthy errors

Decision:

```text
Treat remaining errors as model limitation.
```

Reason:

not deterministic bug.

---

# 14. Day 7 Summary

Day 7 是整个项目第一次真正的系统验证。

它证明：

```text
pipeline 能运行
pipeline 不 crash
pipeline 能抓 hallucination
pipeline 有 measurable performance
```

Day 7 的价值不在 accuracy。

而在：

```text
发现真实失败模式
```

Day 7 发现：

* verifier 能工作
* retrieval precision 是下一阶段问题
* metadata sentence 是真实 bug
* trustworthy false positives 是主要 limitation

最终 Day 7 证明：

```text
系统已经不是 prototype
而是可测量、可调优的研究 pipeline
```

进入 Day 8 时，项目已经具备：

```text
claim_extractor.py ✅
retriever.py ✅
verifier.py ✅
LangGraph agent ✅
smoke test benchmark ✅
```


# Day 8 — Experiment 1: Overall Baseline Evaluation (Complete)

## Day 8 Mission

Day 8 的目标不是新增模块。

Day 1–7 已完成：

* claim extraction
* retrieval
* verification
* aggregation
* LangGraph integration
* smoke test

Day 8 的任务是：

```text
第一次在完整 200 条 eval_set 上运行系统。
```

这是项目第一次真正得到：

```text
full benchmark metrics
```

---

# Day 8 核心问题

Day 7 的 smoke test 只用了：

```text
20 samples
```

虽然能发现 bug。

但不能说明：

```text
整体系统到底表现如何
```

Day 8 要回答：

> 在完整 benchmark 上，这个系统到底准确吗？

---

# Day 8 核心目标

完成：

* 跑完整 200 条 benchmark
* 保存逐条预测结果
* 生成 confusion matrix
* 计算 precision / recall / F1
* 分析 failure modes
* 找出系统级瓶颈
* 为 Day 11 优化提供依据

---

# 1. Experiment Setup

## Script

新增实验脚本：

```text
experiments/exp1_baseline.py
```

---

## 输入数据

来自：

```text
data/eval_set.jsonl
```

规模：

```text
200 samples
```

组成：

| Label         | Count |
| ------------- | ----- |
| trustworthy   | 100   |
| untrustworthy | 100   |

---

## Untrustworthy Breakdown

| Failure Mode                | Count |
| --------------------------- | ----- |
| unsupported_claim           | 25    |
| unsupported_numerical_claim | 25    |
| hallucinated_citation       | 25    |
| contradiction               | 25    |

---

## Evaluation Flow

对于每条样本：

```text
question
answer_to_audit
```

调用：

```python
audit(question, answer_to_audit)
```

记录：

* prediction
* reliability_score
* failure_modes_detected
* n_claims
* elapsed_time

---

## Crash Safety

每 20 条样本：

```text
checkpoint save
```

原因：

避免：

```text
长时间 batch run 中断
```

---

# 2. Day 8 Raw Results

## Confusion Matrix

```text
TP = 96
TN = 17
FP = 83
FN = 4
```

---

## Metrics

| Metric    | Value |
| --------- | ----- |
| Accuracy  | 56.5% |
| Precision | 53.6% |
| Recall    | 96.0% |
| F1        | 68.8% |
| FPR       | 83.0% |

---

## Immediate Observation

系统呈现：

```text
high recall
low precision
```

---

## Meaning

系统几乎不会漏掉 hallucination。

但：

```text
太容易误判 trustworthy
```

---

# 3. Per Failure Mode Performance

## Detection Rate

| Failure Mode                | Detected | Rate |
| --------------------------- | -------- | ---- |
| unsupported_claim           | 24/25    | 96%  |
| unsupported_numerical_claim | 24/25    | 96%  |
| hallucinated_citation       | 23/25    | 92%  |
| contradiction               | 25/25    | 100% |

---

## Interpretation

### unsupported_claim

检测率：

```text
96%
```

说明 verifier 能发现：

```text
新增 unsupported statement
```

---

### unsupported_numerical_claim

检测率：

```text
96%
```

说明 numerical hallucination 很容易被抓。

原因：

* 数字 mismatch 明显
* retrieval 很容易发现不一致

---

### hallucinated_citation

检测率：

```text
92%
```

略低。

原因：

citation sentence 有时被 claim extractor 合并进其他句子。

---

### contradiction

检测率：

```text
100%
```

说明：

```text
CONTRADICTED prompt rule 非常强
```

---

# 4. Result Interpretation

## 系统本质

Day 8 证明：

> 系统是一个高 recall、低 precision detector。

---

## Strength

系统非常擅长：

```text
发现 hallucination
```

---

## Weakness

系统非常容易：

```text
怀疑正常答案
```

---

## Recall = 96%

意味着：

```text
100 个 poisoned answers 中
96 个被抓住
```

---

## FPR = 83%

意味着：

```text
100 个 trustworthy 中
83 个被误报
```

---

## 核心结论

系统不是：

```text
抓不到 hallucination
```

而是：

```text
对 trustworthy 不够宽容
```

---

# 5. Root Cause Analysis

## Root Cause 1 — Threshold Too Strict

当前 aggregation rule：

```python
if reliability_score < 0.7:
    prediction = "untrustworthy"
```

---

## 问题

PubMedQA answer 通常只有：

```text
2–3 claims
```

---

## Example — 3 Claims

```text
2 supported
1 unsupported
```

得到：

```text
reliability_score = 0.667
```

---

## Consequence

```text
0.667 < 0.7
→ untrustworthy
```

即使：

```text
大部分 claim 是正确的
```

---

## Example — 2 Claims

```text
1 supported
1 unsupported
```

得到：

```text
0.5
```

直接：

```text
untrustworthy
```

---

## Observation

短答案对 threshold 非常敏感。

---

# 6. Root Cause 2 — Recommendation Sentences

## Problem

PubMedQA answers 经常包含：

```text
clinical recommendation
conclusion sentence
suggestion
```

---

## Example

```text
criteria lists may be useful in clinical settings
```

---

## Retrieval Problem

retriever 找到：

```text
study results
```

但不是 recommendation rationale。

---

## Consequence

verifier 输出：

```text
UNSUPPORTED
```

---

## Result

reliability_score 降低。

---

# 7. Root Cause 3 — Corpus Structure

## PubMedQA Contexts

更偏向：

```text
study findings
numerical evidence
methods
```

---

## 不包含

```text
clinical recommendation reasoning
```

---

## Consequence

recommendation sentences 系统性难 grounding。

---

# 8. Why Recall Is So High

## Prompt V4

Day 5 prompt 已加入：

* numerical mismatch rule
* citation rule
* contradiction rule

---

## 效果

对于 poisoned answer：

```text
几乎总能找到 mismatch
```

---

## Aggregation Rule

只要：

```text
出现 CONTRADICTED
```

直接：

```text
untrustworthy
```

---

## Result

Recall 非常高。

---

# 9. Day 8 Main Insight

Day 8 最大发现：

问题不在 verifier。

也不在 retriever。

真正问题在：

```text
aggregation threshold
```

---

## Why?

因为：

```text
大多数 FP 来自 1 个 unsupported claim
```

不是：

```text
整个 answer 都错
```

---

# 10. Implication for Day 11

Day 11 将进行优化实验。

---

## Candidate Fix 1 — Lower Threshold

尝试：

```text
0.7 → 0.5
```

---

### Potential Benefit

大量 FP 转为 TN。

---

### Risk

可能降低 recall。

---

## Candidate Fix 2 — Recommendation Filtering

在 claim extractor 中过滤：

```text
non-factual recommendation sentences
```

---

### Potential Benefit

减少 unsupported recommendation。

---

### Risk

可能误删重要 claim。

---

## Day 11 Strategy

优先测试：

```text
threshold adjustment
```

再测试：

```text
claim filtering
```

---

# 11. Files Produced

## Experiment Script

```text
experiments/exp1_baseline.py
```

---

## Analysis Script

```text
experiments/exp1_analyze.py
```

---

## Results

```text
results/exp1_predictions.jsonl
results/exp1_baseline.json
results/exp1_confusion_matrix.png
results/exp1_takeaway.md
```

---

# 12. Completion Status

## Day 8 Completed

### Full 200-sample benchmark

完成。

---

### Metrics Calculation

完成。

---

### Failure Mode Analysis

完成。

---

### Confusion Matrix

完成。

---

### Root Cause Analysis

完成。

---

### Day 11 Optimization Direction

明确。

---

# 13. Day 8 Decisions

## D8.1 — Full benchmark evaluation

Decision:

```text
Run all 200 samples.
```

Reason:

need statistically meaningful metrics.

---

## D8.2 — Checkpoint every 20 samples

Decision:

```text
save partial progress.
```

Reason:

prevent rerunning entire benchmark after interruption.

---

## D8.3 — Prioritize recall over precision

Decision:

```text
accept high FPR initially.
```

Reason:

hallucination detection should minimize missed unsafe outputs.

---

## D8.4 — Treat threshold as optimization variable

Decision:

```text
0.7 is provisional.
```

Reason:

observed to cause FP inflation.

---

# 14. Day 8 Summary

Day 8 是第一次真正的系统 benchmark。

它回答了：

> 系统在完整数据集上到底表现如何？

Day 8 证明：

```text
系统非常擅长发现 hallucination
```

但同时：

```text
系统对 trustworthy answer 不够宽容
```

Day 8 的最大价值不是 accuracy。

而是：

```text
定位系统瓶颈
```

Day 8 找到：

* recall 已非常高
* contradiction rule 有效
* numerical verifier 有效
* threshold 是最大问题
* recommendation claim 是难点

最终 Day 8 建立了：

```text
完整 benchmark baseline
```

未来所有优化都必须与 Day 8 比较。

Day 8 是：

```text
系统性能基线
```

进入 Day 9 时，项目已经具备：

```text
完整 benchmark
confusion matrix
failure mode statistics
error analysis direction
```



## Day 9 — Experiment 2: Failure-Mode Breakdown (Complete)

### D9.1 — Failure mode detection rates

**Method**: Reused Day 8 predictions (`exp1_predictions.jsonl`), grouped by `failure_mode` field, computed detection rate = predicted untrustworthy / total.

**Results**:

| Failure Mode | Detected | Total | Detection Rate |
|---|---:|---:|---:|
| contradiction | 25 | 25 | 100% |
| unsupported_claim | 24 | 25 | 96% |
| unsupported_numerical_claim | 24 | 25 | 96% |
| hallucinated_citation | 23 | 25 | 92% |

All four failure modes detected at ≥ 92%. The system's untrustworthy detection is robust across all injection types.

**Why contradiction is 100%**:  
The V2 prompt's CONTRADICTED rule ("same topic but disagrees → CONTRADICTED") combined with the aggregation rule's CONTRADICTED branch (any CONTRADICTED claim → untrustworthy regardless of reliability score) provides two independent detection paths. Even when the verifier tags the poisoned sentence UNSUPPORTED rather than CONTRADICTED, the reliability score still drops below 0.7.

**Why hallucinated_citation is lowest (92%)**:  
2 citations share surface-level topic overlap with retrieved passages, causing the verifier to incorrectly judge SUPPORTED. V4 prompt's citation Rule 2 catches most but not all — the 2 missed cases involve citations whose journal name appears in unrelated retrieved contexts.

---

### D9.2 — False positive analysis

**Core finding**: FPR = 83% is entirely driven by the 0.7 reliability threshold interacting with short PubMedQA answers.

| Metric | FP samples (n=83) | TN samples (n=17) |
|---|---:|---:|
| Avg reliability score | 0.261 | 1.000 |
| Avg claim count | 2.17 | 1.59 |

**Reliability distribution of FP samples**:

| Reliability Score Range | FP Samples | Share |
|---|---:|---:|
| 0.0–0.3 | 40 | 48% |
| 0.3–0.5 | 37 | 45% |
| 0.5–0.7 | 6 | 7% |
| 0.7+ | 0 | 0% |

**Three structural causes**:

1. **TN samples are short (avg 1.59 claims)**  
   A 1-claim answer where that claim is SUPPORTED yields reliability = 1.0, always passing the threshold. The 17 TN samples are disproportionately 1-claim answers — they pass not because the system is good at grounding them, but because there's only one claim to fail.

2. **Threshold 0.7 is the direct driver**  
   Every single FP sample has reliability < 0.7. This is not a gradual distribution — it's a hard boundary effect. Lowering the threshold to 0.5 would convert the 6 samples in the 0.5–0.7 bucket from FP to TN.

3. **77/83 FP samples have reliability ≤ 0.5**  
   These are "deep false positives" where most claims in a trustworthy answer are judged UNSUPPORTED. Root cause: PubMedQA trustworthy answers contain recommendation/conclusion sentences that retrieval cannot ground directly. These will remain FP regardless of threshold change.

**Implication for Day 11**:

- Lowering threshold 0.7 → 0.5: fixes 6 FP, minimal FN risk
- The remaining 77 FP require either better retrieval or claim filtering
- Priority: test threshold change first, then evaluate recommendation-sentence filtering

---

### D9.3 — Completion status

**Files produced**:

- `experiments/exp2_failure_modes.py`
- `results/exp2_failure_modes.json`
- `results/exp2_table.md`
- `results/exp2_breakdown.png`
- `results/exp2_takeaway.md`

**No model re-run needed**: entire Day 9 analysis reused Day 8 predictions.



## Day 10 — Experiment 3: Verifier Ablation (Complete)

### D10.1 — Ablation setup

**4 configurations on 50-sample stratified subset** (seed=99, 10 per category):

| Config | Retrieval | Self-consistency |
|---|---|---|
| V1: claim-only | ❌ empty evidence | ❌ 1x |
| V2: + retrieval | ✅ top-3 FAISS | ❌ 1x |
| V3: + self-consistency | ❌ empty evidence | ✅ 5x majority vote |
| V4: full system | ✅ top-3 FAISS | ✅ 5x majority vote |

Self-consistency: temperature=0.7, n=5, majority vote on verdict.
Model loaded once onto GPU (14.5GB fp16), reused across all 4 configs
via `MistralVerifier` singleton — fixing the CPU-offload bug from the
first run attempt (D10.0).

---

### D10.2 — Results

| Configuration | Accuracy | Recall | FPR | Latency |
|---|---|---|---|---|
| V1: claim-only | 80.0% | 100.0% | 100.0% | 1.5s |
| V2: + retrieval | **82.0%** | 97.5% | **80.0%** | 3.2s |
| V3: + self-consistency | 80.0% | 100.0% | 100.0% | 7.3s |
| V4: full system | 80.0% | 92.5% | 70.0% | 17.0s |

---

### D10.3 — Finding 1: Retrieval is the only component with clear positive contribution

**V1 → V2** (+retrieval, no consistency):
- Accuracy: +2pp (80% → 82%)
- FPR: -20pp (100% → 80%)
- Recall: -2.5pp (100% → 97.5%) — minor trade-off
- Latency: +1.7s (1.5s → 3.2s)

Retrieval grounding gives the verifier topically-relevant context for
trustworthy claims, allowing it to correctly judge them SUPPORTED rather
than defaulting to UNSUPPORTED. The 2.5pp recall drop is one sample
(id=139, unsupported_claim) that retrieval accidentally grounded —
evidence returned for the poisoned claim happened to support it.

---

### D10.4 — Finding 2: Self-consistency alone has zero contribution

**V1 vs V3** (same accuracy, same recall, same FPR, same everything):
- Accuracy: 80.0% vs 80.0%
- FPR: 100% vs 100%
- Only difference: latency 1.5s → 7.3s (5x slower, no benefit)

**Root cause**: Without retrieval, the verifier operates on empty
evidence for all claims. With empty evidence, the model has no
information signal to vary across samples — 5 draws at temperature=0.7
produce consistent verdicts (usually UNSUPPORTED for most trustworthy
claims). Majority vote of identical wrong answers is still wrong.
Self-consistency only helps when there is genuine uncertainty in the
input signal; empty evidence provides none.

---

### D10.5 — Finding 3: Full system (V4) has lowest FPR but worst recall

**V4** (retrieval + consistency):
- FPR: 70% — best of all 4 configs (-30pp vs V1)
- Recall: 92.5% — worst of all 4 configs (-7.5pp vs V1)
- Latency: 17.0s — 11x slower than V1

The FPR improvement comes from retrieval (same as V2). The recall
degradation is caused by self-consistency: in 3 cases (id=139, 162,
167), 5 stochastic samples at temperature=0.7 produced a majority vote
of SUPPORTED for poisoned claims — the fabricated content happened to
align with retrieved evidence in enough samples to flip the majority.
This is a known failure mode of self-consistency: variance in sampling
introduces noise that can reverse correct deterministic judgments.

---

### D10.6 — Best configuration: V2 (retrieval only)

**V2 dominates on the accuracy-recall-latency trade-off**:
- Highest accuracy (82%)
- Second-highest recall (97.5%, only 0.5pp below V1/V3)
- FPR meaningfully reduced (80% vs 100% for V1/V3)
- Latency only 3.2s vs 17.0s for V4

**Conclusion**: Retrieval grounding is necessary and sufficient.
Self-consistency adds latency without accuracy benefit, and with
retrieval it introduces harmful variance on borderline cases.

---

### D10.7 — Engineering bug: CPU offload on first run attempt

**Problem**: First ablation run showed GPU=2.45GB and latency=66s/sample
(vs expected 14.5GB and ~1.5s). Root cause: the ablation script loaded
`AutoModelForCausalLM` independently from the `verifier.py` singleton,
triggering a second model load that exceeded available contiguous GPU
memory and caused automatic CPU offloading.

**Fix**: Refactored ablation script to reuse `MistralVerifier` singleton
via `_ensure_loaded()`, guaranteeing a single fp16 model on GPU shared
across all 4 configurations. Latency restored to 1.5s/sample for V1.

**Lesson**: Multiple independent model loads in the same process compete
for GPU memory. Always reuse singletons across experiments in the same
process.

---

### D10.8 — Completion status

**Files produced**:
- `experiments/exp3_ablation.py`
- `data/ablation_set.jsonl`
- `results/exp3_ablation.json`
- `results/exp3_table.md`
- `results/exp3_takeaway.md`



## Day 11 — Optimization (Complete)

### D11.1 — Optimization hypothesis and target

**Diagnosis from Day 8–9**:

- FPR = 83% is the primary weakness
- Day 9 FP reliability distribution showed 6 samples in the 0.5–0.7 range
- Hypothesis: lowering threshold 0.7 → 0.5 would convert those 6 FP to TN with minimal recall impact

**Variable changed**: `reliability_score < 0.7` → `reliability_score < 0.5` in `aggregate_node` in `src/agent.py`.

One-line change, all else constant.

---

### D11.2 — Result: rolled back

| Threshold | Accuracy | Recall | FPR | FN |
|---|---:|---:|---:|---:|
| 0.7 (baseline) | 56.5% | 96.0% | 83.0% | 4 |
| 0.5 (attempt) | 56.5% | 74.0% | 61.0% | 26 |

Accuracy unchanged. FPR improved by 22pp, but Recall degraded by 22pp.

The trade-off is perfectly symmetric — no net benefit. Rolled back to 0.7.

**Per-failure-mode at threshold = 0.5**:

| Failure Mode | Baseline | Threshold 0.5 | Change |
|---|---:|---:|---:|
| unsupported_claim | 96% | 64% | -32pp |
| hallucinated_citation | 92% | 60% | -32pp |
| unsupported_numerical | 96% | 80% | -16pp |
| contradiction | 100% | 92% | -8pp |

The system loses its core detection strength across all failure modes.

---

### D11.3 — Root cause: threshold tuning is a blunt instrument here

**Why the trade-off is symmetric**:

Day 9 showed FP reliability clusters at 0.0–0.5: 77/83 = 93% of FP samples.

These are trustworthy answers where retrieval cannot ground recommendation/conclusion sentences. Their reliability is usually 0.0–0.3, not 0.5–0.7. No achievable threshold fixes them.

The 6 samples in the 0.5–0.7 range were converted FP → TN by threshold = 0.5, but simultaneously 22 untrustworthy samples were converted TP → FN. Their poisoned claims had reliability just above 0.5 due to partial grounding.

**The distribution is bimodal**:

- Trustworthy FP: cluster at 0.0–0.3  
  Ungroundable sentences; retrieval returns nothing relevant.
- Untrustworthy FN risk: cluster at 0.5–0.7  
  Poisoned claims partially grounded by topic-adjacent evidence.

Any threshold between 0.5 and 0.7 helps one group by roughly the same amount it hurts the other. Threshold tuning cannot break this symmetry.

---

### D11.4 — True fix identified: future work

The correct intervention is upstream in `claim_extractor.py`: filter unverifiable sentence types before they reach the verifier.

Examples include:

- Recommendations
- Policy statements
- Meta-claims such as “to the best of our knowledge”

This would raise trustworthy reliability scores without affecting untrustworthy reliability scores, breaking the symmetry.

This was not implemented in Day 11 because:

1. It requires defining a reliable heuristic for “unverifiable sentence” without introducing new false negatives.
2. Day 7's NCT/registration filter showed that targeted filtering works but requires careful case analysis.
3. A rushed implementation risks regression.
4. The finding itself — threshold tuning is ineffective due to bimodal reliability distribution — is the Day 11 research contribution.

---

### D11.5 — Completion status

**Final system state**: threshold = 0.7, original setting.

All metrics remain unchanged from the Day 8 baseline.

**Files produced**:

- `results/exp_optimization.md` — full optimization log with hypothesis, result, root cause, and lesson
- `src/agent_v1_threshold07.py` — backup of original agent before threshold change

**Lesson**: In retrieval-augmented verification systems, aggregation threshold tuning is ineffective when the primary failure mode is upstream ungroundable claim types. Fix the retrieval or extraction layer first.




## Day 12 — Failure Case Deep Dive (Complete)

### D12.1 — Case selection methodology

Selected 5 cases from 87 total failures (83 FP + 4 FN) in Experiment 1,
prioritizing cases that: (a) cover both error directions, (b) have
distinct root causes at different pipeline layers, and (c) reveal
non-obvious system behavior worth discussing in interviews.

| Case | id | Type | Failure Mode | Root Cause Layer |
|------|-----|------|-------------|-----------------|
| 1 | 4 | FP | trustworthy CONTRADICTED | Retrieval cross-study conflict |
| 2 | 11 | FP | trustworthy CONTRADICTED | Retrieval cross-study conflict |
| 3 | 7 | FP | meta-claim + hedged language | Claim extraction + Verifier |
| 4 | 139 | FN | numerical fabrication missed | Verifier number-checking |
| 5 | 166 | FN | citation diluted by long answer | Aggregation threshold |

---

### D12.2 — Key findings

**Finding 1: Cross-study retrieval conflict is the dominant FP cause**

Cases 1 and 2 share the same root cause: the answer reports a finding
from one study ("no significant difference," "non-HDL-C predicts MACE"),
but the retrieval corpus contains passages from other studies that reach
different conclusions (combination chemo efficacy, LDL-C guidelines).
The verifier correctly applies the CONTRADICTED rule — the evidence does
disagree with the claim — but the disagreement is between studies, not
between the claim and its own evidence.

This is structurally unfixable with the current global retrieval corpus.
The correct fix is to scope retrieval to source-paper contexts only
(available in PubMedQA's `context` field but not used in the current
architecture). This single change would likely eliminate the majority
of the 83 FP cases.

**Finding 2: Meta-claims and hedged language are unverifiable by design**

Case 3 ("the authors strongly support the suggestion that...") represents
a class of claims that cannot be grounded in external evidence — they
assert the authors' own conclusion, which would require the paper itself
as evidence. Similarly, hedged claims ("suggests a possible link")
require partial-support handling that the current binary
SUPPORTED/UNSUPPORTED distinction cannot express.

**Finding 3: Numerical fabrication detection has a coverage gap**

Case 4 (fabricated "63% improvement") showed reliability=1.0 — the
highest-confidence false negative. V4 prompt's Rule 1 ("exact number
must appear in evidence") failed because the retrieved passage contained
percentage figures in a related context. The verifier pattern-matched
on semantic similarity rather than numerical exactness. A post-processing
regex check (does the specific percentage appear verbatim in any evidence
passage?) would catch this class of failure.

**Finding 4: Citation fabrication needs a dedicated aggregation rule**

Case 5 showed that a hallucinated citation in a 5-claim answer only
costs 0.2 reliability points (4/5 claims SUPPORTED = 0.8 > 0.7
threshold). The citation was correctly identified as UNSUPPORTED, but
the aggregation rule treats it identically to any other weak claim.
Citations are categorically different from factual claims — fabricating
a source is a stronger hallucination than asserting an unverifiable fact.
A dedicated aggregation branch ("if any citation-format claim is
UNSUPPORTED → untrustworthy") would fix this without affecting other
failure modes.

---

### D12.3 — Pipeline layer attribution

| Layer | Cases | Implication |
|-------|-------|------------|
| Retrieval (corpus scoping) | 1, 2 | Highest leverage fix — global corpus creates cross-study conflicts |
| Claim extraction (meta-claims) | 3 | Filter "authors suggest/conclude" sentences |
| Verifier (number-checking) | 4 | Post-processing regex for exact percentage match |
| Aggregation (citation rule) | 5 | Dedicated branch for citation-format UNSUPPORTED |

**No single fix addresses all 5 cases.** The 4 distinct root causes
require 4 separate interventions, each at a different pipeline layer.
This validates the modular architecture (D1.1) — each layer can be
improved independently.

---

### D12.4 — Completion status

**File produced**: `reports/failure_cases.md`
- 5 full case studies with question, answer, per-claim analysis,
  root cause, and fix recommendation
- Summary table with pipeline layer attribution
- ~1800 words total
