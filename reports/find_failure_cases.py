"""
Helper: list all failure cases from exp1 predictions for manual selection.
"""

import json

PRED_PATH = "results/exp1_predictions.jsonl"
EVAL_PATH = "data/eval_set.jsonl"

with open(PRED_PATH) as f:
    preds = {json.loads(l)["id"]: json.loads(l) for l in f}

with open(EVAL_PATH) as f:
    evals = {json.loads(l)["id"]: json.loads(l) for l in f}

fp = [p for p in preds.values()
      if p["label"] == "trustworthy" and p["prediction"] == "untrustworthy"]
fn = [p for p in preds.values()
      if p["label"] == "untrustworthy" and p["prediction"] == "trustworthy"]

print(f"Total FP (trustworthy → untrustworthy): {len(fp)}")
print(f"Total FN (untrustworthy → trustworthy): {len(fn)}")

print("\n=== FALSE POSITIVES (sample) ===")
for p in fp[:15]:
    e = evals[p["id"]]
    print(f"  id={p['id']:3d}  rel={p['reliability_score']}  "
          f"modes={p['failure_modes_detected']}  "
          f"claims={p['n_claims']}")
    print(f"    answer: {e['answer_to_audit'][:120]}")
    print()

print("\n=== FALSE NEGATIVES ===")
for p in fn:
    e = evals[p["id"]]
    print(f"  id={p['id']:3d}  rel={p['reliability_score']}  "
          f"failure_mode={p['failure_mode']}  "
          f"claims={p['n_claims']}")
    print(f"    answer: {e['answer_to_audit'][:120]}")
    print()
