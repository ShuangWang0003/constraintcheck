
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




