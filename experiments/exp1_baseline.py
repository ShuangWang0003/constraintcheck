"""
Experiment 1: Overall baseline on full 200-sample eval set.
"""

import json
import os
import time

from src.agent import audit

EVAL_PATH        = "data/eval_set.jsonl"
OUTPUT_PATH      = "results/exp1_predictions.jsonl"
CHECKPOINT_PATH  = "results/exp1_checkpoint.jsonl"
CHECKPOINT_EVERY = 20


def load_eval_set():
    with open(EVAL_PATH) as f:
        return [json.loads(line) for line in f]


def load_checkpoint():
    if not os.path.exists(CHECKPOINT_PATH):
        return {}, []
    done = {}
    rows = []
    with open(CHECKPOINT_PATH) as f:
        for line in f:
            r = json.loads(line)
            done[r["id"]] = True
            rows.append(r)
    return done, rows


def save_checkpoint(rows):
    os.makedirs("results", exist_ok=True)
    with open(CHECKPOINT_PATH, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def main():
    os.makedirs("results", exist_ok=True)

    samples      = load_eval_set()
    done, results = load_checkpoint()

    if done:
        print(f"[resume] Found checkpoint: {len(done)} samples already done.")

    remaining = [s for s in samples if s["id"] not in done]
    total     = len(samples)

    print("=" * 78)
    print(f"Experiment 1: Full baseline — {total} samples total, {len(remaining)} remaining")
    print("=" * 78)

    t_start = time.time()

    for i, sample in enumerate(remaining, start=len(done) + 1):
        t0 = time.time()

        try:
            result        = audit(sample["question"], sample["answer_to_audit"])
            prediction    = result["prediction"]
            reliability   = result["reliability_score"]
            failure_modes = result["failure_modes"]
            n_claims      = len(result["claims"])
            error         = None
        except Exception as e:
            prediction    = "ERROR"
            reliability   = None
            failure_modes = []
            n_claims      = 0
            error         = str(e)

        elapsed = time.time() - t0
        label   = sample["label"]
        correct = (prediction == label)
        mark    = "✓" if correct else ("E" if error else "✗")

        print(f"[{i:3d}/{total}] {mark}  "
              f"id={sample['id']:3d}  "
              f"label={label:13s}  pred={prediction:13s}  "
              f"mode={str(sample.get('failure_mode')):30s}  "
              f"({elapsed:.1f}s)")

        if error:
            print(f"          ERROR: {error}")

        row = {
            "id":                    sample["id"],
            "label":                 label,
            "failure_mode":          sample.get("failure_mode"),
            "prediction":            prediction,
            "correct":               correct,
            "reliability_score":     reliability,
            "failure_modes_detected": failure_modes,
            "n_claims":              n_claims,
            "elapsed":               round(elapsed, 2),
            "error":                 error,
        }
        results.append(row)

        if i % CHECKPOINT_EVERY == 0:
            save_checkpoint(results)
            elapsed_total = time.time() - t_start
            rate = elapsed_total / (i - len(done))
            eta  = rate * (total - i)
            print(f"  [checkpoint] {i}/{total} done — ETA {eta/60:.1f} min")

    save_checkpoint(results)

    with open(OUTPUT_PATH, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    total_time = time.time() - t_start
    n_correct  = sum(1 for r in results if r["correct"])
    n_error    = sum(1 for r in results if r["error"])

    print()
    print("=" * 78)
    print(f"Done. {len(results)} samples in {total_time/60:.1f} min")
    print(f"Accuracy: {n_correct}/{len(results)} ({n_correct/len(results)*100:.1f}%)")
    print(f"Errors:   {n_error}")
    print(f"Output:   {OUTPUT_PATH}")
    print("Next: python -m experiments.exp1_analyze")


if __name__ == "__main__":
    main()
