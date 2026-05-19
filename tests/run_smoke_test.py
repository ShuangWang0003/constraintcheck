"""
Day 7: 20-sample smoke test.

Evaluates the full end-to-end pipeline (claim extraction → retrieval →
verification → aggregation) on 20 stratified eval_set samples.

Metric: prediction accuracy (trustworthy / untrustworthy) — not per-claim
verdict accuracy. This is the system-level signal that matters for Day 8.
"""

import json
import random
import time
from collections import Counter

from src.agent import audit


SEED = 7
SMOKE_PATH = "data/smoke_test.jsonl"
EVAL_PATH  = "data/eval_set.jsonl"

STRATA = {
    "trustworthy":                 5,
    "unsupported_claim":           4,
    "unsupported_numerical_claim": 4,
    "hallucinated_citation":       4,
    "contradiction":               3,
}


# =========================================================================
# Build smoke_test.jsonl (idempotent)
# =========================================================================
def build_smoke_set():
    rng = random.Random(SEED)

    with open(EVAL_PATH) as f:
        all_samples = [json.loads(line) for line in f]

    buckets = {
        "trustworthy": [
            s for s in all_samples if s["label"] == "trustworthy"
        ],
        "unsupported_claim": [
            s for s in all_samples if s["failure_mode"] == "unsupported_claim"
        ],
        "unsupported_numerical_claim": [
            s for s in all_samples if s["failure_mode"] == "unsupported_numerical_claim"
        ],
        "hallucinated_citation": [
            s for s in all_samples if s["failure_mode"] == "hallucinated_citation"
        ],
        "contradiction": [
            s for s in all_samples if s["failure_mode"] == "contradiction"
        ],
    }

    picks = []
    for category, n in STRATA.items():
        chosen = rng.sample(buckets[category], n)
        picks.extend(chosen)

    with open(SMOKE_PATH, "w") as f:
        for s in picks:
            f.write(json.dumps(s) + "\n")

    print(f"[setup] Wrote {len(picks)} samples to {SMOKE_PATH}")
    return picks


# =========================================================================
# Main
# =========================================================================
def main():
    # Build smoke set
    samples = build_smoke_set()

    print()
    print("=" * 78)
    print(f"Day 7 Smoke Test — {len(samples)} samples, full pipeline")
    print("=" * 78)
    print()

    results = []
    t_total = time.time()

    for i, sample in enumerate(samples, 1):
        question        = sample["question"]
        answer_to_audit = sample["answer_to_audit"]
        label           = sample["label"]           # "trustworthy" / "untrustworthy"
        failure_mode    = sample.get("failure_mode")

        t0 = time.time()
        try:
            result = audit(question, answer_to_audit)
            prediction = result["prediction"]
            elapsed    = time.time() - t0
            error      = None
        except Exception as e:
            prediction = "ERROR"
            elapsed    = time.time() - t0
            error      = str(e)

        is_correct = (prediction == label)
        mark = "✓" if is_correct else "✗"

        print(f"[{i:2d}/20] {mark}  "
              f"label={label:13s}  pred={prediction:13s}  "
              f"mode={str(failure_mode):30s}  "
              f"id={sample['id']:3d}  ({elapsed:.1f}s)")

        if error:
            print(f"        ERROR: {error}")

        if not is_correct and not error:
            print(f"        claims={result.get('claims', [])}")
            print(f"        reliability={result.get('reliability_score')}  "
                  f"failure_modes={result.get('failure_modes')}")
            verdicts = result.get("verdicts", [])
            for j, (claim, v) in enumerate(
                zip(result.get("claims", []), verdicts), 1
            ):
                print(f"        [{j}] {claim[:80]}")
                print(f"             → {v['verdict']} | {v['reasoning'][:80]}")

        results.append({
            "id":          sample["id"],
            "label":       label,
            "prediction":  prediction,
            "correct":     is_correct,
            "failure_mode": failure_mode,
            "elapsed":     round(elapsed, 2),
            "error":       error,
        })

    total_time = time.time() - t_total

    # ---- Summary ---------------------------------------------------------
    n_correct = sum(1 for r in results if r["correct"])
    n_error   = sum(1 for r in results if r["error"])
    accuracy  = n_correct / len(results)

    print()
    print("=" * 78)
    print(f"Overall: {n_correct}/{len(results)} correct ({accuracy*100:.0f}%)")
    print(f"Errors:  {n_error}/{len(results)}")
    print(f"Time:    {total_time:.1f}s total  ({total_time/len(results):.1f}s/sample)")
    print()

    # Per-stratum breakdown
    print("Per-stratum accuracy:")
    for category in STRATA:
        cat_results = [
            r for r in results
            if (r["failure_mode"] == category) or
               (category == "trustworthy" and r["label"] == "trustworthy")
        ]
        if not cat_results:
            continue
        n = sum(1 for r in cat_results if r["correct"])
        print(f"  {category:30s}  {n}/{len(cat_results)}  "
              f"({100*n/len(cat_results):.0f}%)")

    # Confusion matrix
    print()
    print("Confusion matrix:")
    tp = sum(1 for r in results if r["label"] == "untrustworthy" and r["prediction"] == "untrustworthy")
    tn = sum(1 for r in results if r["label"] == "trustworthy"   and r["prediction"] == "trustworthy")
    fp = sum(1 for r in results if r["label"] == "trustworthy"   and r["prediction"] == "untrustworthy")
    fn = sum(1 for r in results if r["label"] == "untrustworthy" and r["prediction"] == "trustworthy")
    print(f"  TP (correctly caught untrustworthy): {tp}")
    print(f"  TN (correctly passed trustworthy):   {tn}")
    print(f"  FP (false alarm on trustworthy):     {fp}")
    print(f"  FN (missed untrustworthy):           {fn}")

    if (tp + fp) > 0:
        precision = tp / (tp + fp)
        print(f"  Precision: {precision:.2f}")
    if (tp + fn) > 0:
        recall = tp / (tp + fn)
        print(f"  Recall:    {recall:.2f}")
    if (tn + fp) > 0:
        fpr = fp / (tn + fp)
        print(f"  FPR:       {fpr:.2f}")

    # Save results
    out_path = "results/smoke_test_results.jsonl"
    import os
    os.makedirs("results", exist_ok=True)
    with open(out_path, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    print()
    print(f"Results saved to {out_path}")

    # Exit code for CI
    import sys
    sys.exit(0 if accuracy >= 0.65 else 1)


if __name__ == "__main__":
    main()
