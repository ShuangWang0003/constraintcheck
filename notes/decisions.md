
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
