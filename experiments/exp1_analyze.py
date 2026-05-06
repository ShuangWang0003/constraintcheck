"""
Experiment 1: Analyze predictions and compute baseline metrics.

Input:  results/exp1_predictions.jsonl
Output: results/exp1_baseline.json
        results/exp1_confusion_matrix.png
        results/exp1_takeaway.md
"""

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PREDICTIONS_PATH = "results/exp1_predictions.jsonl"
OUTPUT_JSON      = "results/exp1_baseline.json"
OUTPUT_PNG       = "results/exp1_confusion_matrix.png"
OUTPUT_TAKEAWAY  = "results/exp1_takeaway.md"


def load_predictions():
    with open(PREDICTIONS_PATH) as f:
        return [json.loads(line) for line in f]


def compute_metrics(results):
    tp = sum(1 for r in results if r["label"] == "untrustworthy" and r["prediction"] == "untrustworthy")
    tn = sum(1 for r in results if r["label"] == "trustworthy"   and r["prediction"] == "trustworthy")
    fp = sum(1 for r in results if r["label"] == "trustworthy"   and r["prediction"] == "untrustworthy")
    fn = sum(1 for r in results if r["label"] == "untrustworthy" and r["prediction"] == "trustworthy")

    total     = len(results)
    accuracy  = (tp + tn) / total
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)
    fpr       = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    return {
        "total": total,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "accuracy":  round(accuracy,  4),
        "precision": round(precision, 4),
        "recall":    round(recall,    4),
        "f1":        round(f1,        4),
        "fpr":       round(fpr,       4),
    }


def plot_confusion_matrix(tp, tn, fp, fn, path):
    matrix = np.array([[tn, fp],
                        [fn, tp]])
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(matrix, cmap="Blues")

    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["Pred: Trustworthy", "Pred: Untrustworthy"], fontsize=11)
    ax.set_yticklabels(["Actual: Trustworthy", "Actual: Untrustworthy"], fontsize=11)
    ax.set_title("ConstraintCheck — Confusion Matrix (Exp 1 Baseline)", fontsize=12)

    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(matrix[i, j]),
                    ha="center", va="center",
                    fontsize=20, fontweight="bold",
                    color="white" if matrix[i, j] > matrix.max() / 2 else "black")

    plt.colorbar(im, ax=ax)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")


def per_failure_mode(results):
    modes = ["unsupported_claim", "unsupported_numerical_claim",
             "hallucinated_citation", "contradiction"]
    out = {}
    for mode in modes:
        subset = [r for r in results if r["failure_mode"] == mode]
        if not subset:
            continue
        detected = sum(1 for r in subset if r["prediction"] == "untrustworthy")
        out[mode] = {
            "total":          len(subset),
            "detected":       detected,
            "detection_rate": round(detected / len(subset), 4),
        }
    return out


def main():
    os.makedirs("results", exist_ok=True)

    results = load_predictions()
    valid   = [r for r in results if r["prediction"] != "ERROR"]
    errors  = [r for r in results if r["prediction"] == "ERROR"]

    print(f"Loaded {len(results)} predictions ({len(errors)} errors, {len(valid)} valid)")

    metrics = compute_metrics(valid)
    modes   = per_failure_mode(valid)

    print()
    print("=" * 60)
    print("Experiment 1 — Overall Baseline")
    print("=" * 60)
    print(f"  Accuracy:  {metrics['accuracy']*100:.1f}%")
    print(f"  Precision: {metrics['precision']*100:.1f}%")
    print(f"  Recall:    {metrics['recall']*100:.1f}%")
    print(f"  F1:        {metrics['f1']*100:.1f}%")
    print(f"  FPR:       {metrics['fpr']*100:.1f}%")
    print()
    print(f"  TP={metrics['tp']}  TN={metrics['tn']}  FP={metrics['fp']}  FN={metrics['fn']}")
    print()
    print("Per-failure-mode detection rate:")
    for mode, d in modes.items():
        print(f"  {mode:35s}  {d['detected']}/{d['total']}  ({d['detection_rate']*100:.0f}%)")

    plot_confusion_matrix(
        metrics["tp"], metrics["tn"],
        metrics["fp"], metrics["fn"],
        OUTPUT_PNG,
    )

    output = {"metrics": metrics, "per_failure_mode": modes, "n_errors": len(errors)}
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved: {OUTPUT_JSON}")

    takeaway = f"""# Experiment 1 — Baseline Takeaway

## Numbers
- Accuracy:  {metrics['accuracy']*100:.1f}%
- Precision: {metrics['precision']*100:.1f}%
- Recall:    {metrics['recall']*100:.1f}%
- F1:        {metrics['f1']*100:.1f}%
- FPR:       {metrics['fpr']*100:.1f}%

## Confusion Matrix
|                       | Pred Trustworthy | Pred Untrustworthy |
|-----------------------|------------------|--------------------|
| Actual Trustworthy    | TN={metrics['tn']}             | FP={metrics['fp']}                |
| Actual Untrustworthy  | FN={metrics['fn']}             | TP={metrics['tp']}                |

## Per-failure-mode Detection Rate
"""
    for mode, d in modes.items():
        takeaway += f"- {mode}: {d['detected']}/{d['total']} ({d['detection_rate']*100:.0f}%)\n"

    takeaway += "\n## Key Observations\n- (fill in after seeing numbers)\n"

    with open(OUTPUT_TAKEAWAY, "w") as f:
        f.write(takeaway)
    print(f"Saved: {OUTPUT_TAKEAWAY}")


if __name__ == "__main__":
    main()
