"""
Experiment 2: Failure-mode breakdown analysis.

Reuses Day 8 predictions — no model re-run needed.

Input:  results/exp1_predictions.jsonl
Output: results/exp2_failure_modes.json
        results/exp2_table.md
        results/exp2_breakdown.png
        results/exp2_takeaway.md
"""

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PREDICTIONS_PATH = "results/exp1_predictions.jsonl"
OUTPUT_JSON      = "results/exp2_failure_modes.json"
OUTPUT_TABLE     = "results/exp2_table.md"
OUTPUT_PNG       = "results/exp2_breakdown.png"
OUTPUT_TAKEAWAY  = "results/exp2_takeaway.md"

FAILURE_MODES = [
    "unsupported_claim",
    "unsupported_numerical_claim",
    "hallucinated_citation",
    "contradiction",
]


def load_predictions():
    with open(PREDICTIONS_PATH) as f:
        return [json.loads(line) for line in f]


def analyze_failure_modes(results):
    out = {}
    for mode in FAILURE_MODES:
        subset = [r for r in results if r["failure_mode"] == mode]
        detected = sum(1 for r in subset if r["prediction"] == "untrustworthy")
        missed   = [r for r in subset if r["prediction"] == "trustworthy"]
        out[mode] = {
            "total":          len(subset),
            "detected":       detected,
            "missed":         len(missed),
            "detection_rate": round(detected / len(subset), 4) if subset else 0,
            "missed_ids":     [r["id"] for r in missed],
        }
    return out


def analyze_false_positives(results):
    """Analyze the 83 trustworthy samples incorrectly flagged."""
    fp = [r for r in results
          if r["label"] == "trustworthy" and r["prediction"] == "untrustworthy"]
    tn = [r for r in results
          if r["label"] == "trustworthy" and r["prediction"] == "trustworthy"]

    fp_reliability = [r["reliability_score"] for r in fp if r["reliability_score"] is not None]
    tn_reliability = [r["reliability_score"] for r in tn if r["reliability_score"] is not None]
    fp_nclaims     = [r["n_claims"] for r in fp]
    tn_nclaims     = [r["n_claims"] for r in tn]

    return {
        "n_fp": len(fp),
        "n_tn": len(tn),
        "fp_avg_reliability": round(sum(fp_reliability) / len(fp_reliability), 3) if fp_reliability else None,
        "tn_avg_reliability": round(sum(tn_reliability) / len(tn_reliability), 3) if tn_reliability else None,
        "fp_avg_claims":      round(sum(fp_nclaims) / len(fp_nclaims), 2) if fp_nclaims else None,
        "tn_avg_claims":      round(sum(tn_nclaims) / len(tn_nclaims), 2) if tn_nclaims else None,
        "fp_reliability_dist": {
            "0.0-0.3": sum(1 for r in fp_reliability if r <= 0.3),
            "0.3-0.5": sum(1 for r in fp_reliability if 0.3 < r <= 0.5),
            "0.5-0.7": sum(1 for r in fp_reliability if 0.5 < r <= 0.7),
            "0.7+":    sum(1 for r in fp_reliability if r > 0.7),
        },
    }


def plot_breakdown(mode_results, path):
    modes      = list(mode_results.keys())
    rates      = [mode_results[m]["detection_rate"] * 100 for m in modes]
    labels     = [m.replace("_", "\n") for m in modes]
    colors     = ["#2196F3" if r >= 95 else "#FF9800" if r >= 85 else "#F44336"
                  for r in rates]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(labels, rates, color=colors, edgecolor="white", linewidth=0.5)

    ax.set_ylim(0, 110)
    ax.set_ylabel("Detection Rate (%)", fontsize=12)
    ax.set_title("ConstraintCheck — Failure Mode Detection Rate (Exp 2)", fontsize=12)
    ax.axhline(y=70, color="gray", linestyle="--", linewidth=1, label="70% baseline target")
    ax.legend(fontsize=10)

    for bar, rate, mode in zip(bars, rates, modes):
        n     = mode_results[mode]["detected"]
        total = mode_results[mode]["total"]
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1.5,
                f"{rate:.0f}%\n({n}/{total})",
                ha="center", va="bottom", fontsize=11, fontweight="bold")

    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")


def main():
    os.makedirs("results", exist_ok=True)

    results      = load_predictions()
    valid        = [r for r in results if r["prediction"] != "ERROR"]
    mode_results = analyze_failure_modes(valid)
    fp_analysis  = analyze_false_positives(valid)

    # ---- Print summary ---------------------------------------------------
    print("=" * 65)
    print("Experiment 2 — Failure Mode Breakdown")
    print("=" * 65)
    print()
    print(f"{'Failure Mode':<35} {'Detected':>8} {'Total':>6} {'Rate':>6}")
    print("-" * 65)
    for mode, d in mode_results.items():
        print(f"{mode:<35} {d['detected']:>8} {d['total']:>6} {d['detection_rate']*100:>5.0f}%")
    print()

    print("False Positive Analysis (trustworthy → untrustworthy):")
    print(f"  FP count:              {fp_analysis['n_fp']}")
    print(f"  TN count:              {fp_analysis['n_tn']}")
    print(f"  FP avg reliability:    {fp_analysis['fp_avg_reliability']}")
    print(f"  TN avg reliability:    {fp_analysis['tn_avg_reliability']}")
    print(f"  FP avg n_claims:       {fp_analysis['fp_avg_claims']}")
    print(f"  TN avg n_claims:       {fp_analysis['tn_avg_claims']}")
    print(f"  FP reliability dist:   {fp_analysis['fp_reliability_dist']}")

    # ---- Plot ------------------------------------------------------------
    plot_breakdown(mode_results, OUTPUT_PNG)

    # ---- Save JSON -------------------------------------------------------
    output = {"failure_modes": mode_results, "false_positive_analysis": fp_analysis}
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved: {OUTPUT_JSON}")

    # ---- Table -----------------------------------------------------------
    table = "# Experiment 2 — Failure Mode Detection Rate\n\n"
    table += f"| Failure Mode | Sample Size | Detected | Detection Rate |\n"
    table += f"|---|---|---|---|\n"
    for mode, d in mode_results.items():
        table += (f"| {mode} | {d['total']} | {d['detected']} "
                  f"| {d['detection_rate']*100:.0f}% |\n")
    with open(OUTPUT_TABLE, "w") as f:
        f.write(table)
    print(f"Saved: {OUTPUT_TABLE}")

    # ---- Takeaway --------------------------------------------------------
    best_mode  = max(mode_results, key=lambda m: mode_results[m]["detection_rate"])
    worst_mode = min(mode_results, key=lambda m: mode_results[m]["detection_rate"])

    takeaway = f"""# Experiment 2 — Failure Mode Takeaway

## Detection Rate Summary

| Failure Mode | Detection Rate |
|---|---|
"""
    for mode, d in mode_results.items():
        takeaway += f"| {mode} | {d['detection_rate']*100:.0f}% |\n"

    takeaway += f"""
## Key Findings

**Best detected**: `{best_mode}` ({mode_results[best_mode]['detection_rate']*100:.0f}%)
- Contradiction templates append generic disagreement sentences that retrieval
  cannot ground in the corpus. The V2 prompt's CONTRADICTED rule catches these
  via the "same topic but disagrees" decision rule, and the aggregation rule's
  CONTRADICTED branch provides an additional catch regardless of reliability score.

**Worst detected**: `{worst_mode}` ({mode_results[worst_mode]['detection_rate']*100:.0f}%)
- Some hallucinated citations share surface-level topic overlap with retrieved
  passages (e.g., a citation about "Annals of Clinical Medicine" retrieves
  a passage from a clinical study), causing the verifier to incorrectly judge
  SUPPORTED. V4 prompt's citation rule (Rule 2) catches most but not all cases.

## False Positive Analysis

- {fp_analysis['n_fp']}/100 trustworthy samples incorrectly flagged
- FP avg reliability score: {fp_analysis['fp_avg_reliability']} vs TN avg: {fp_analysis['tn_avg_reliability']}
- FP avg claim count: {fp_analysis['fp_avg_claims']} vs TN avg: {fp_analysis['tn_avg_claims']}
- Reliability distribution of FP samples: {fp_analysis['fp_reliability_dist']}

**Implication**: FP samples have systematically lower reliability scores,
confirming that the 0.7 threshold is the primary driver of false positives.
Day 11 optimization: lower threshold to 0.5 and re-evaluate.
"""
    with open(OUTPUT_TAKEAWAY, "w") as f:
        f.write(takeaway)
    print(f"Saved: {OUTPUT_TAKEAWAY}")


if __name__ == "__main__":
    main()
