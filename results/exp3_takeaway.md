# Experiment 3 — Ablation Takeaway

## Results Table

| Configuration | Accuracy | Recall | FPR | Latency |
|---|---|---|---|---|
| V1: claim-only | 80.0% | 100.0% | 100.0% | 1.5s |
| V2: + retrieval | 82.0% | 97.5% | 80.0% | 3.2s |
| V3: + self-consistency | 80.0% | 100.0% | 100.0% | 7.3s |
| V4: full system | 80.0% | 92.5% | 70.0% | 17.0s |

## Key Findings

- Retrieval contribution (V1→V2): +2.0pp accuracy
- Self-consistency contribution (V1→V3): +0.0pp accuracy
- Full system vs claim-only (V1→V4): +0.0pp accuracy
