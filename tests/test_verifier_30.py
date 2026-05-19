"""
Step 5.6: Run verifier on 30 real eval_set samples.

This is the first scaling test beyond the curated golden cases.
Goal: >= 70% (21/30) accuracy. Below that, prompt needs more work.

Sampling: stratified random — 6 trustworthy + 6 each of 4 failure modes,
then we discard the trustworthy/untrustworthy distinction and just check
whether the verifier's per-claim verdict matches the expected truth signal.
"""

import json
import random
import time
from collections import Counter

from src.claim_extractor import extract_claims
from src.retriever import retrieve
from src.verifier import verify


SAMPLE_SIZE = 30
SEED = 7


def expected_verdict_for_claim(sample: dict, claim_text: str) -> str:
    """
    Determine the expected verdict for a single claim.
    
    Heuristic:
      - If sample is trustworthy: every claim should be SUPPORTED
        (each is a real PubMedQA long_answer sentence)
      - If sample is untrustworthy: most claims are still SUPPORTED 
        (original sentences), but the LAST claim is the poisoned one
        and should be UNSUPPORTED or CONTRADICTED depending on mode
    
    For Step 5.6, we only evaluate ONE claim per sample — the most likely
    "decision claim". We pick:
      - For trustworthy: a random middle claim (any one should be SUPPORTED)
      - For untrustworthy: the LAST claim (which is the appended poisoned content)
    """
    pass  # see main() for the actual logic


def main():
    rng = random.Random(SEED)

    with open("data/eval_set.jsonl") as f:
        all_samples = [json.loads(line) for line in f]

    # Stratified sampling: 6 from each category
    buckets = {
        "trustworthy":                 [s for s in all_samples if s["label"] == "trustworthy"],
        "unsupported_claim":           [s for s in all_samples if s["failure_mode"] == "unsupported_claim"],
        "unsupported_numerical_claim": [s for s in all_samples if s["failure_mode"] == "unsupported_numerical_claim"],
        "hallucinated_citation":       [s for s in all_samples if s["failure_mode"] == "hallucinated_citation"],
        "contradiction":               [s for s in all_samples if s["failure_mode"] == "contradiction"],
    }
    
    picks = []
    for category, pool in buckets.items():
        chosen = rng.sample(pool, 6)
        for s in chosen:
            picks.append((category, s))

    print("=" * 78)
    print(f"Step 5.6: Verifier on {len(picks)} real eval_set samples (stratified)")
    print("=" * 78)
    print(f"6 each of: {list(buckets.keys())}")
    print()

    # Track per-category results
    per_category = {cat: {"correct": 0, "total": 0, "details": []} for cat in buckets}
    
    t0 = time.time()
    for i, (category, sample) in enumerate(picks, 1):
        claims = extract_claims(sample["answer_to_audit"])
        if not claims:
            print(f"[{i:2d}/30] [{category}] id={sample['id']} — no claims extracted, SKIP")
            continue

        # For trustworthy: check the FIRST claim (any should be SUPPORTED)
        # For poisoned: check the LAST claim (the appended poison)
        # For modified-numerical (no append): also LAST as proxy
        if category == "trustworthy":
            target_claim = claims[0]
            expected = "SUPPORTED"
        else:
            target_claim = claims[-1]
            if category == "contradiction":
                expected = "CONTRADICTED"
            else:
                expected = "UNSUPPORTED"

        # Retrieve and verify
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
        print(f"[{i:2d}/30] [{category:30s}] id={sample['id']:3d}  "
              f"{mark}  expected={expected:13s}  got={predicted}")

    total_time = time.time() - t0

    # ---- Summary ---------------------------------------------------------
    total_correct = sum(d["correct"] for d in per_category.values())
    total_evaluated = sum(d["total"] for d in per_category.values())

    print()
    print("=" * 78)
    print(f"Overall: {total_correct}/{total_evaluated} correct ({100*total_correct/total_evaluated:.0f}%)")
    print(f"Time: {total_time:.1f}s ({total_time/total_evaluated:.1f}s/case)")
    print()

    print("Per-category accuracy:")
    for cat, d in per_category.items():
        if d["total"] == 0:
            print(f"  {cat:30s}  no samples evaluated")
        else:
            print(f"  {cat:30s}  {d['correct']}/{d['total']}  ({100*d['correct']/d['total']:.0f}%)")

    # ---- Failure analysis ------------------------------------------------
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
