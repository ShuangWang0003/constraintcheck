# Day 11 Optimization — Threshold Tuning

## Hypothesis
Lowering reliability threshold from 0.7 → 0.5 would convert the 6 FP
samples in the 0.5-0.7 reliability range to TN, improving FPR with
minimal recall impact.

## Experiment

| Threshold | Accuracy | Recall | FPR  | FN |
|-----------|----------|--------|------|----|
| 0.7 (baseline) | 56.5% | 96.0% | 83.0% | 4  |
| 0.5 (attempt)  | 56.5% | 74.0% | 61.0% | 26 |

## Result: Rolled back to 0.7

Threshold=0.5 reduced FPR by 22pp but simultaneously reduced Recall by
22pp. Net accuracy unchanged (56.5%). The trade-off is symmetric and
undesirable: the system loses its core strength (high recall) without
gaining meaningful precision.

## Root Cause Analysis

The Day 9 FP reliability distribution showed:
  - 0.0-0.3: 40 samples (48%)
  - 0.3-0.5: 37 samples (45%)
  - 0.5-0.7:  6 samples  (7%)

The 77 samples with reliability ≤ 0.5 are not fixable via threshold —
their reliability is low because retrieval cannot ground
recommendation/conclusion sentences in the PubMedQA corpus. These
sentences get UNSUPPORTED regardless of evidence quality. No threshold
change addresses this upstream retrieval failure.

The 6 samples in 0.5-0.7 were converted from FP to TN by threshold=0.5,
but this also converted 22 untrustworthy samples from TP to FN (their
poisoned claims had reliability just above 0.5 due to partial support).

## Lesson

Threshold tuning is a blunt instrument when the reliability distribution
is bimodal: trustworthy FP samples cluster at 0.0-0.5 (ungroundable
sentences), untrustworthy FN samples cluster at 0.5-0.7 (partially
grounded poisoned claims). Any threshold that helps one group hurts the
other by the same amount.

## True Fix (future work)

The correct intervention is upstream: filter unverifiable sentence types
(recommendations, policy statements, meta-claims) from claim extraction
before they reach the verifier. This would raise trustworthy reliability
scores without changing untrustworthy reliability scores, breaking the
symmetry that makes threshold tuning ineffective.
