# Experiment 1 — Baseline Takeaway

## Numbers
- Accuracy:  56.5%
- Precision: 53.6%
- Recall:    96.0%
- F1:        68.8%
- FPR:       83.0%

## Confusion Matrix
|                       | Pred Trustworthy | Pred Untrustworthy |
|-----------------------|------------------|--------------------|
| Actual Trustworthy    | TN=17             | FP=83                |
| Actual Untrustworthy  | FN=4             | TP=96                |

## Per-failure-mode Detection Rate
- unsupported_claim: 24/25 (96%)
- unsupported_numerical_claim: 24/25 (96%)
- hallucinated_citation: 23/25 (92%)
- contradiction: 25/25 (100%)

## Key Observations
- (fill in after seeing numbers)
