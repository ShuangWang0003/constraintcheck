
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

