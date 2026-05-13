# Experiment 2 — Failure Mode Takeaway

## Detection Rate Summary

| Failure Mode | Detection Rate |
|---|---|
| unsupported_claim | 96% |
| unsupported_numerical_claim | 96% |
| hallucinated_citation | 92% |
| contradiction | 100% |

## Key Findings

**Best detected**: `contradiction` (100%)
- Contradiction templates append generic disagreement sentences that retrieval
  cannot ground in the corpus. The V2 prompt's CONTRADICTED rule catches these
  via the "same topic but disagrees" decision rule, and the aggregation rule's
  CONTRADICTED branch provides an additional catch regardless of reliability score.

**Worst detected**: `hallucinated_citation` (92%)
- Some hallucinated citations share surface-level topic overlap with retrieved
  passages (e.g., a citation about "Annals of Clinical Medicine" retrieves
  a passage from a clinical study), causing the verifier to incorrectly judge
  SUPPORTED. V4 prompt's citation rule (Rule 2) catches most but not all cases.

## False Positive Analysis

- 83/100 trustworthy samples incorrectly flagged
- FP avg reliability score: 0.261 vs TN avg: 1.0
- FP avg claim count: 2.17 vs TN avg: 1.59
- Reliability distribution of FP samples: {'0.0-0.3': 40, '0.3-0.5': 37, '0.5-0.7': 6, '0.7+': 0}

**Implication**: FP samples have systematically lower reliability scores,
confirming that the 0.7 threshold is the primary driver of false positives.
Day 11 optimization: lower threshold to 0.5 and re-evaluate.
