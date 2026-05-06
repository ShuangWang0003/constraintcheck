"""
Experiment 3: Verifier ablation study.

Compares 4 system configurations on a 50-sample stratified subset:
  V1: claim-only      (no retrieval, 1x verify)
  V2: + retrieval     (top-3 evidence, 1x verify)
  V3: + consistency   (no retrieval, 5x majority vote)
  V4: full system     (top-3 evidence, 5x majority vote)

Output: results/exp3_ablation.json
        results/exp3_table.md
        results/exp3_takeaway.md
"""

import json
import os
import random
import time
from collections import Counter

import torch

from src.claim_extractor import extract_claims
from src.retriever import retrieve
from src.verifier import MistralVerifier, PROMPT_TEMPLATE, _format_evidence, _parse_verdict

EVAL_PATH       = "data/eval_set.jsonl"
ABLATION_PATH   = "data/ablation_set.jsonl"
OUTPUT_JSON     = "results/exp3_ablation.json"
OUTPUT_TABLE    = "results/exp3_table.md"
OUTPUT_TAKEAWAY = "results/exp3_takeaway.md"

SAMPLES_PER_CATEGORY = 10
SEED            = 99
N_CONSISTENCY   = 5
TEMPERATURE     = 0.7


# =========================================================================
# Shared verifier — reuses the singleton that loads to GPU correctly
# =========================================================================
_verifier = None

def get_verifier():
    global _verifier
    if _verifier is None:
        _verifier = MistralVerifier()
        _verifier._ensure_loaded()
        mem = torch.cuda.memory_allocated() / 1e9
        print(f"[Ablation] Verifier ready. GPU: {mem:.2f} GB")
    return _verifier


def verify_once(claim, evidence, do_sample=False, temperature=1.0):
    v = get_verifier()
    prompt  = PROMPT_TEMPLATE.format(
        claim=claim,
        evidence_block=_format_evidence(evidence),
    )
    inputs = v.tokenizer(prompt, return_tensors="pt").to(v.model.device)
    kwargs = dict(max_new_tokens=80, pad_token_id=v.tokenizer.eos_token_id)
    if do_sample:
        kwargs["do_sample"]   = True
        kwargs["temperature"] = temperature
    else:
        kwargs["do_sample"] = False

    with torch.no_grad():
        output = v.model.generate(**inputs, **kwargs)

    full_text   = v.tokenizer.decode(output[0], skip_special_tokens=True)
    prompt_text = v.tokenizer.decode(inputs["input_ids"][0], skip_special_tokens=True)
    return _parse_verdict(full_text[len(prompt_text):])


def verify_majority(claim, evidence, n=N_CONSISTENCY):
    verdicts = []
    for _ in range(n):
        r = verify_once(claim, evidence, do_sample=True, temperature=TEMPERATURE)
        verdicts.append(r["verdict"])
    winner = Counter(verdicts).most_common(1)[0][0]
    return {"verdict": winner, "reasoning": f"majority({verdicts})"}


# =========================================================================
# Aggregation
# =========================================================================
def aggregate(verdicts):
    if not verdicts:
        return {"reliability_score": 0.0, "prediction": "untrustworthy"}
    supported    = sum(1 for v in verdicts if v["verdict"] == "SUPPORTED")
    contradicted = any(v["verdict"] == "CONTRADICTED" for v in verdicts)
    score        = supported / len(verdicts)
    prediction   = "untrustworthy" if (contradicted or score < 0.7) else "trustworthy"
    return {"reliability_score": round(score, 3), "prediction": prediction}


# =========================================================================
# Build ablation set
# =========================================================================
def build_ablation_set():
    rng = random.Random(SEED)
    with open(EVAL_PATH) as f:
        all_samples = [json.loads(line) for line in f]

    buckets = {
        "trustworthy":                 [s for s in all_samples if s["label"] == "trustworthy"],
        "unsupported_claim":           [s for s in all_samples if s["failure_mode"] == "unsupported_claim"],
        "unsupported_numerical_claim": [s for s in all_samples if s["failure_mode"] == "unsupported_numerical_claim"],
        "hallucinated_citation":       [s for s in all_samples if s["failure_mode"] == "hallucinated_citation"],
        "contradiction":               [s for s in all_samples if s["failure_mode"] == "contradiction"],
    }

    picks = []
    for category, pool in buckets.items():
        chosen = rng.sample(pool, SAMPLES_PER_CATEGORY)
        picks.extend(chosen)

    with open(ABLATION_PATH, "w") as f:
        for s in picks:
            f.write(json.dumps(s) + "\n")
    print(f"[setup] Wrote {len(picks)} samples to {ABLATION_PATH}")
    return picks


# =========================================================================
# Run one configuration
# =========================================================================
def run_config(samples, use_retrieval, use_consistency, label):
    print(f"\n{'='*65}")
    print(f"Config: {label}  "
          f"(retrieval={use_retrieval}, consistency={use_consistency})")
    print(f"{'='*65}")

    results  = []
    t0_total = time.time()

    for i, sample in enumerate(samples, 1):
        t0     = time.time()
        claims = extract_claims(sample["answer_to_audit"])

        if not claims:
            pred = "untrustworthy"
            rel  = 0.0
        else:
            verdicts = []
            for claim in claims:
                evidence = retrieve(claim, top_k=3) if use_retrieval else []
                v = verify_majority(claim, evidence) if use_consistency \
                    else verify_once(claim, evidence)
                verdicts.append(v)
            agg  = aggregate(verdicts)
            pred = agg["prediction"]
            rel  = agg["reliability_score"]

        elapsed = time.time() - t0
        correct = (pred == sample["label"])
        mark    = "✓" if correct else "✗"

        print(f"  [{i:2d}/50] {mark}  id={sample['id']:3d}  "
              f"label={sample['label']:13s}  pred={pred:13s}  "
              f"({elapsed:.1f}s)")

        results.append({
            "id":            sample["id"],
            "label":         sample["label"],
            "failure_mode":  sample.get("failure_mode"),
            "prediction":    pred,
            "correct":       correct,
            "reliability_score": rel,
            "elapsed":       round(elapsed, 2),
        })

    total_time = time.time() - t0_total
    n_correct  = sum(1 for r in results if r["correct"])

    tp = sum(1 for r in results if r["label"] == "untrustworthy" and r["prediction"] == "untrustworthy")
    tn = sum(1 for r in results if r["label"] == "trustworthy"   and r["prediction"] == "trustworthy")
    fp = sum(1 for r in results if r["label"] == "trustworthy"   and r["prediction"] == "untrustworthy")
    fn = sum(1 for r in results if r["label"] == "untrustworthy" and r["prediction"] == "trustworthy")

    recall   = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fpr      = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    accuracy = n_correct / len(results)
    avg_time = total_time / len(results)

    summary = {
        "label":            label,
        "use_retrieval":    use_retrieval,
        "use_consistency":  use_consistency,
        "accuracy":         round(accuracy, 4),
        "recall":           round(recall, 4),
        "fpr":              round(fpr, 4),
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "avg_latency":      round(avg_time, 2),
        "total_time":       round(total_time, 1),
    }

    print(f"\n  → accuracy={accuracy*100:.1f}%  recall={recall*100:.1f}%  "
          f"fpr={fpr*100:.1f}%  latency={avg_time:.1f}s/sample")

    return summary, results


# =========================================================================
# Main
# =========================================================================
def main():
    os.makedirs("results", exist_ok=True)

    # Pre-load model once onto GPU before any config runs
    get_verifier()

    samples = build_ablation_set()

    configs = [
        (False, False, "V1: claim-only"),
        (True,  False, "V2: + retrieval"),
        (False, True,  "V3: + self-consistency"),
        (True,  True,  "V4: full system"),
    ]

    all_summaries = []
    for use_retrieval, use_consistency, label in configs:
        summary, _ = run_config(
            samples, use_retrieval, use_consistency, label
        )
        all_summaries.append(summary)

    # ---- Ablation table --------------------------------------------------
    print("\n" + "=" * 75)
    print("Ablation Table")
    print("=" * 75)
    print(f"{'Configuration':<30} {'Accuracy':>9} {'Recall':>7} "
          f"{'FPR':>6} {'Latency':>9}")
    print("-" * 75)
    for s in all_summaries:
        print(f"{s['label']:<30} {s['accuracy']*100:>8.1f}% "
              f"{s['recall']*100:>6.1f}% {s['fpr']*100:>5.1f}% "
              f"{s['avg_latency']:>8.1f}s")

    # ---- Save JSON -------------------------------------------------------
    with open(OUTPUT_JSON, "w") as f:
        json.dump(all_summaries, f, indent=2)
    print(f"\nSaved: {OUTPUT_JSON}")

    # ---- Table MD --------------------------------------------------------
    table  = "# Experiment 3 — Verifier Ablation\n\n"
    table += "| Configuration | Accuracy | Recall | FPR | Latency/sample |\n"
    table += "|---|---|---|---|---|\n"
    for s in all_summaries:
        table += (f"| {s['label']} | {s['accuracy']*100:.1f}% | "
                  f"{s['recall']*100:.1f}% | {s['fpr']*100:.1f}% | "
                  f"{s['avg_latency']:.1f}s |\n")
    with open(OUTPUT_TABLE, "w") as f:
        f.write(table)
    print(f"Saved: {OUTPUT_TABLE}")

    # ---- Takeaway --------------------------------------------------------
    v1 = all_summaries[0]
    v2 = all_summaries[1]
    v3 = all_summaries[2]
    v4 = all_summaries[3]

    retrieval_gain   = (v2["accuracy"] - v1["accuracy"]) * 100
    consistency_gain = (v3["accuracy"] - v1["accuracy"]) * 100
    full_gain        = (v4["accuracy"] - v1["accuracy"]) * 100

    takeaway = f"""# Experiment 3 — Ablation Takeaway

## Results Table

| Configuration | Accuracy | Recall | FPR | Latency |
|---|---|---|---|---|
| V1: claim-only | {v1['accuracy']*100:.1f}% | {v1['recall']*100:.1f}% | {v1['fpr']*100:.1f}% | {v1['avg_latency']:.1f}s |
| V2: + retrieval | {v2['accuracy']*100:.1f}% | {v2['recall']*100:.1f}% | {v2['fpr']*100:.1f}% | {v2['avg_latency']:.1f}s |
| V3: + self-consistency | {v3['accuracy']*100:.1f}% | {v3['recall']*100:.1f}% | {v3['fpr']*100:.1f}% | {v3['avg_latency']:.1f}s |
| V4: full system | {v4['accuracy']*100:.1f}% | {v4['recall']*100:.1f}% | {v4['fpr']*100:.1f}% | {v4['avg_latency']:.1f}s |

## Key Findings

- Retrieval contribution (V1→V2): {retrieval_gain:+.1f}pp accuracy
- Self-consistency contribution (V1→V3): {consistency_gain:+.1f}pp accuracy
- Full system vs claim-only (V1→V4): {full_gain:+.1f}pp accuracy
"""
    with open(OUTPUT_TAKEAWAY, "w") as f:
        f.write(takeaway)
    print(f"Saved: {OUTPUT_TAKEAWAY}")


if __name__ == "__main__":
    main()
