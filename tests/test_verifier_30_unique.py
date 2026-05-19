"""
Step 5.6 (revised): Verifier on 30 real eval_set samples with deduplication.

Discovery from initial run: poisoner template reuse caused the same poisoned
claim text to appear in multiple samples, multiplying single semantic failures
across the test set. This script enforces unique poisoned-claim text within
each failure-mode bucket, yielding a more accurate per-mode accuracy estimate.
"""

import json
import random
import time
from collections import Counter

from src.claim_extractor import extract_claims
from src.retriever import retrieve
from src.verifier import verify


SAMPLES_PER_CATEGORY = 6
SEED = 7


def get_target_claim(sample, category):
    """For trustworthy: first claim. For poisoned: last claim (the appended poison)."""
    claims = extract_claims(sample["answer_to_audit"])
    if not claims:
        return None
    if category == "trustworthy":
        return claims[0]
    return claims[-1]


def main():
    rng = random.Random(SEED)

    with open("data/eval_set.jsonl") as f:
        all_samples = [json.loads(line) for line in f]

    buckets = {
        "trustworthy":                 [s for s in all_samples if s["label"] == "trustworthy"],
        "unsupported_claim":           [s for s in all_samples if s["failure_mode"] == "unsupported_claim"],
        "unsupported_numerical_claim": [s for s in all_samples if s["failure_mode"] == "unsupported_numerical_claim"],
        "hallucinated_citation":       [s for s in all_samples if s["failure_mode"] == "hallucinated_citation"],
        "contradiction":               [s for s in all_samples if s["failure_mode"] == "contradiction"],
    }

    # Deduplicate by target claim text within each bucket
    picks = []
    for category, pool in buckets.items():
        rng.shuffle(pool)
        seen_claims = set()
        chosen = []
        for s in pool:
            target = get_target_claim(s, category)
            if target is None:
                continue
            # Normalize for dedup (case + whitespace)
            key = " ".join(target.lower().split())
            if key in seen_claims:
                continue
            seen_claims.add(key)
            chosen.append((s, target))
            if len(chosen) >= SAMPLES_PER_CATEGORY:
                break
        if len(chosen) < SAMPLES_PER_CATEGORY:
            print(f"WARNING: only found {len(chosen)} unique-claim samples for {category}")
        for s, target in chosen:
            picks.append((category, s, target))

    print("=" * 78)
    print(f"Step 5.6 (revised): Verifier on {len(picks)} samples with UNIQUE poisoned claims")
    print("=" * 78)
    print()

    per_category = {cat: {"correct": 0, "total": 0, "details": []} for cat in buckets}
    
    t0 = time.time()
    for i, (category, sample, target_claim) in enumerate(picks, 1):
        if category == "trustworthy":
            expected = "SUPPORTED"
        elif category == "contradiction":
            expected = "CONTRADICTED"
        else:
            expected = "UNSUPPORTED"

        evidence = retrieve(target_claim, top_k=3)
        result = verify(target_claim, evidence)
        predicted = result["verdict"]
        is_correct = (predicted == expected)

        per_category[category]["total"] += 1
        if is_correct:
            per_category[category]["correct"] += 1

        per_category[category]["details"].append({
            "id": sample["id"],
            "claim": target_claim,
            "expected": expected,
            "predicted": predicted,
            "correct": is_correct,
            "reasoning": result["reasoning"],
        })

        mark = "✓" if is_correct else "✗"
        print(f"[{i:2d}/{len(picks)}] [{category:30s}] id={sample['id']:3d}  "
              f"{mark}  expected={expected:13s}  got={predicted}")

    total_time = time.time() - t0

    total_correct = sum(d["correct"] for d in per_category.values())
    total_evaluated = sum(d["total"] for d in per_category.values())

    print()
    print("=" * 78)
    print(f"Overall: {total_correct}/{total_evaluated} correct ({100*total_correct/total_evaluated:.0f}%)")
    print(f"Time: {total_time:.1f}s ({total_time/total_evaluated:.1f}s/case)")
    print()

    print("Per-category accuracy (UNIQUE claims only):")
    for cat, d in per_category.items():
        if d["total"] == 0:
            print(f"  {cat:30s}  no samples evaluated")
        else:
            print(f"  {cat:30s}  {d['correct']}/{d['total']}  ({100*d['correct']/d['total']:.0f}%)")

    failures = [(cat, det) for cat, d in per_category.items() for det in d["details"] if not det["correct"]]
    if failures:
        print()
        print("=" * 78)
        print(f"Failed cases ({len(failures)}):")
        print("=" * 78)
        for cat, det in failures:
            print(f"\n[{cat}]  id={det['id']}")
            print(f"  CLAIM:    {det['claim'][:200]}")
            print(f"  EXPECTED: {det['expected']}")
            print(f"  GOT:      {det['predicted']}")
            print(f"  REASONING: {det['reasoning'][:250]}")


if __name__ == "__main__":
    main()
