# Day 2 — Evaluation Set Construction & Dataset Integrity

## Day 2 Mission

Day 2 focused on building the **core evaluation dataset** that powers the remaining 13 days of experimentation.

The goal was not simply to generate examples, but to create a **scientifically defensible evaluation protocol**.

The final objective was:

* Build a reproducible evaluation dataset
* Create trustworthy and untrustworthy answer pools
* Simulate multiple hallucination / failure behaviors
* Ensure zero data leakage
* Produce retrieval-ready evidence corpus
* Document all design decisions
* Guarantee reproducibility
* Validate sample quality manually

Final Day 2 outcome:

```text
200 labeled evaluation samples
100 trustworthy
100 untrustworthy
4 balanced failure modes
Retrieval corpus generated
Full reproducibility
Leakage-free sampling
```

---

# 1. Dataset Acquisition

## Goal

Acquire the PubMedQA labeled dataset and inspect whether it is suitable for a retrieval-grounded verification benchmark.

---

## Script Created

```text
tests/download_pubmedqa.py
```

---

## Dataset Used

Dataset:

```text
PubMedQA — pqa_labeled split
```

Size:

```text
1000 samples
```

---

## Why PubMedQA?

PubMedQA contains:

* Real biomedical questions
* Literature-grounded evidence passages
* Human-written long-form answers
* PubMed paper identifiers

This makes it suitable for:

* retrieval
* claim extraction
* hallucination detection
* evidence verification

---

# 2. Dataset Inspection

## Script Created

```text
tests/inspect_pubmedqa.py
```

---

## Objective

Understand the internal schema of PubMedQA.

---

## Structure Found

Each sample contains:

```text
pubid
question
context
long_answer
final_decision
```

Key fields used for Day 2:

| Field       | Purpose                 |
| ----------- | ----------------------- |
| pubid       | unique paper identifier |
| question    | evaluation prompt       |
| context     | retrieval evidence      |
| long_answer | source answer           |

---

## Important Observation

`long_answer` is the most useful component because it:

* contains multiple claims
* reflects realistic biomedical reasoning
* provides a natural hallucination injection target

---

# 3. Long Answer Distribution Analysis

## Goal

Measure answer length distribution.

---

## Discovery

Long answer lengths vary heavily.

Observed distribution:

```text
minimum = 8 words
median ≈ 37 words
mean ≈ 40 words
```

---

## Problem Found

Very short answers are unstable for later claim extraction.

Example:

```text
Yes.
```

or:

```text
Results varied.
```

These answers cannot produce multiple claims.

---

## Decision

Only keep answers with:

```text
long_answer >= 25 words
```

---

## Result

Filtering outcome:

```text
1000 total
812 eligible
```

---

## Why This Matters

This filtering protects Day 3 claim extraction.

Without it:

* 1-claim answers dominate
* reliability score becomes unstable
* aggregation becomes noisy

---

# 4. Numerical Coverage Analysis

## Script Created

```text
tests/check_numerical_coverage.py
```

---

## Goal

Measure how often biomedical answers naturally contain numbers.

---

## Results

```text
21.4% contain numbers
2.7% contain percentages
```

---

## Impact

This discovery strongly affected numerical hallucination design.

Initial assumption:

```text
Many answers contain editable numbers
```

Reality:

```text
Most answers do not.
```

---

# 5. Poisoner Module

## File Built

```text
src/poisoner.py
```

---

## Purpose

Generate synthetic hallucinated answers.

This module transforms:

```text
trustworthy → untrustworthy
```

while preserving readability.

---

## Failure Modes Implemented

### 1. unsupported_claim

Injects unsupported biomedical statements.

Templates:

```text
5 handcrafted claim templates
```

Example:

```text
Original:
The treatment reduced inflammation.

Poisoned:
The treatment reduced inflammation and significantly improved long-term neurological recovery.
```

---

### 2. unsupported_numerical_claim

Introduces numerical hallucinations.

Two subtypes:

#### A. modified_existing_number

Edits existing numerical values.

Example:

```text
30% → 72%
```

---

#### B. fabricated_percentage

Adds completely invented percentages.

Example:

```text
Treatment improved survival by 84%.
```

---

### 3. hallucinated_citation

Adds fake citation references.

Example:

```text
(Smith et al., 2017)
```

when citation does not exist.

---

### 4. contradiction

Injects contradictory statements.

Example:

```text
Original:
Drug reduced symptoms.

Poisoned:
Drug reduced symptoms but showed no measurable clinical improvement.
```

---

# 6. Numerical Poisoning Design

## Problem

Not every number is safe to edit.

---

## Skip Rules Added

Four skip rules were implemented.

### Skip 1 — Years

Example:

```text
1997
2012
2020
```

---

### Skip 2 — Ages

Example:

```text
70 years old
```

---

### Skip 3 — Context Labels

Example:

```text
Phase 2
Group 1
```

---

### Skip 4 — Figure/Table References

Example:

```text
Figure 3
Table 1
```

---

## Why?

Prevent low-quality hallucinations.

Bad example:

```text
70 years → 140 years
```

---

## Numerical Perturbation

Modification range:

```text
1.5x – 2.6x
```

Purpose:

* noticeable
* believable
* not absurd

---

# 7. Eval Set Builder

## File Built

```text
src/build_eval_set.py
```

---

## Purpose

Create the final benchmark dataset.

---

## Output Files

```text
data/eval_set.jsonl
data/corpus.jsonl
```

---

# 8. Eval Set Construction

## Final Distribution

```text
200 total samples
```

---

## Trustworthy Samples

```text
100
```

Built directly from original PubMedQA answers.

---

## Untrustworthy Samples

```text
100
```

Generated via poisoners.

---

## Failure Mode Balance

```text
unsupported_claim: 25
unsupported_numerical_claim: 25
hallucinated_citation: 25
contradiction: 25
```

---

# 9. Disjoint Pool Design

## Core Rule

```text
trustworthy ∩ untrustworthy = ∅
```

---

## Why?

Prevent retrieval leakage.

---

## Risk Without Disjointness

If same paper appears in both pools:

```text
Retriever sees original evidence.
Verifier gains unfair advantage.
```

---

## Implementation

Dataset shuffled once:

```text
seed=42
```

Then split into disjoint chunks.

---

## Runtime Assertion

Implemented overlap validation.

Result:

```text
0 overlapping pubids
```

---

# 10. Numerical Subtype Recruitment

## Initial Attempt

Random sampling produced:

```text
modified_existing_number = 4
fabricated_percentage = 21
```

---

## Problem

Too few modified-number examples.

This weakens subtype analysis.

---

## Fix

Targeted recruitment added.

Unused pool scanned for safe numerical candidates.

---

## Final Distribution

```text
modified_existing_number = 12
fabricated_percentage = 13
```

---

# 11. Retrieval Corpus

## Output

```text
data/corpus.jsonl
```

---

## Purpose

Provide retrieval database for Day 4.

---

## Source

All PubMedQA context passages.

---

## Deduplication

Used first 200 chars as dedup key.

---

## Final Size

```text
3347 passages
```

---

# 12. Decision Logging

## File

```text
notes/decisions.md
```

---

## Day 2 Decisions Added

### D2.1

Rename numerical mode.

---

### D2.2

Add skip rules.

---

### D2.3

Add perturbation factor.

---

### D2.4

Add fabrication diversity.

---

### D2.5

Add reproducible rng.

---

### D2.6

Disjoint pools.

---

### D2.7

Length filter.

---

### D2.8

Best-effort quota.

---

### D2.9

Targeted recruitment.

---

# 13. Sanity Check

## Added Internal Validation

Poisoner tested across:

```text
4 failure modes
2 numerical branches
```

---

## Purpose

Ensure:

* success flag works
* metadata returned
* poisoning stable
* no crashes

---

# 14. Manual Inspection

## Samples Reviewed

```text
5 poisoned examples
```

---

## Coverage

Included:

* unsupported claim
* modified number
* fabricated percentage
* hallucinated citation
* contradiction

---

## Bug Found

```text
IL-7 → IL-14
```

Problem:

Biomedical identifiers incorrectly modified.

---

## Future Fix

Add biomedical identifier skip rule.

Examples:

```text
IL-7
CD4
CD8
p53
```

---

# 15. Quality Guarantees

## Dataset Guarantees

### Balanced labels

```text
100 trustworthy
100 untrustworthy
```

---

### Balanced failure modes

```text
25 each
```

---

### Zero overlap

```text
0 shared pubids
```

---

### Reproducible

```text
seed=42
```

---

### Retrieval corpus ready

```text
3347 passages
```

---

# 16. Day 2 Final Deliverables

## Scripts

```text
tests/download_pubmedqa.py
tests/inspect_pubmedqa.py
tests/check_numerical_coverage.py
src/poisoner.py
src/build_eval_set.py
```

---

## Data

```text
data/eval_set.jsonl
data/corpus.jsonl
```

---

## Notes

```text
notes/decisions.md
```

---

# 17. Day 2 Summary

Day 2 established the experimental foundation of the entire project.

This was not merely dataset generation.

It was the construction of:

* an evaluation protocol
* a hallucination benchmark
* a retrieval-safe verification dataset
* a reproducible experimental environment

The Day 2 dataset becomes the foundation for:

* Day 3 claim extraction
* Day 4 retrieval
* Day 5 verification
* Day 6 aggregation
* Day 7 threshold tuning
* Day 8 evaluation metrics
* Day 9 error analysis
* Day 10 ablation
* Day 11 reporting
* Day 12 refinement
* Day 13 interpretation
* Day 14 final deliverable

Day 2 created the infrastructure that the rest of the project depends on.
