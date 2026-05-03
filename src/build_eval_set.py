"""
Build the evaluation set: 200 samples (100 trustworthy + 100 untrustworthy)
across 4 failure modes, with reproducible seeded sampling.

Output files:
  data/eval_set.jsonl  — 200 eval samples with ground truth labels
  data/corpus.jsonl    — retrieval corpus (PubMedQA contexts)

Run:
  python -m src.build_eval_set
"""

import json
import random
import os
from collections import Counter
from datasets import load_dataset

from src.poisoner import (
    inject_unsupported_claim,
    inject_unsupported_numerical_claim,
    inject_hallucinated_citation,
    inject_contradiction,
)


# ---- Configuration -------------------------------------------------------
SEED = 42
N_TRUSTWORTHY = 100
N_PER_FAILURE_MODE = 25
MIN_ANSWER_WORDS = 25

EVAL_PATH = "data/eval_set.jsonl"
CORPUS_PATH = "data/corpus.jsonl"


def is_eligible(example: dict) -> bool:
    return len(example["long_answer"].split()) >= MIN_ANSWER_WORDS


def make_trustworthy(example: dict, idx: int) -> dict:
    return {
        "id": idx,
        "pubid": example["pubid"],
        "question": example["question"],
        "answer_to_audit": example["long_answer"],
        "context_passages": example["context"]["contexts"],
        "label": "trustworthy",
        "failure_mode": None,
        "metadata": {},
    }


def make_untrustworthy(
    example: dict,
    idx: int,
    failure_mode: str,
    poisoner_fn,
    rng: random.Random,
    poisoner_kwargs: dict = None,
) -> dict:
    if poisoner_kwargs is None:
        poisoner_kwargs = {}
    poisoned, success, meta = poisoner_fn(example["long_answer"], rng, **poisoner_kwargs)
    if not success or poisoned is None:
        return None
    return {
        "id": idx,
        "pubid": example["pubid"],
        "question": example["question"],
        "answer_to_audit": poisoned,
        "context_passages": example["context"]["contexts"],
        "label": "untrustworthy",
        "failure_mode": failure_mode,
        "metadata": meta,
    }


def main():
    print(f"[build_eval_set] seed={SEED}")
    rng = random.Random(SEED)

    # ---- Load PubMedQA ---------------------------------------------------
    print("[1/6] Loading PubMedQA pqa_labeled from cache...")
    ds = load_dataset("pubmed_qa", "pqa_labeled")
    examples = list(ds["train"])
    print(f"      Loaded {len(examples)} examples.")

    # ---- Filter eligible samples ----------------------------------------
    eligible = [ex for ex in examples if is_eligible(ex)]
    print(f"[2/6] Filtered eligible (long_answer >= {MIN_ANSWER_WORDS} words): "
          f"{len(eligible)}/{len(examples)}")

    rng.shuffle(eligible)

    # ---- Allocate trustworthy chunk first --------------------------------
    trust_chunk = eligible[:N_TRUSTWORTHY]
    remaining = eligible[N_TRUSTWORTHY:]
    print(f"      Trustworthy chunk: {len(trust_chunk)} samples")
    print(f"      Untrustworthy candidate pool: {len(remaining)} samples")

    # ---- Allocate untrustworthy chunks (4 modes × 25, sequential) -------
    print("[3/6] Allocating untrustworthy chunks...")
    cursor = 0
    unsup_chunk = remaining[cursor:cursor + N_PER_FAILURE_MODE]; cursor += N_PER_FAILURE_MODE
    num_chunk   = remaining[cursor:cursor + N_PER_FAILURE_MODE]; cursor += N_PER_FAILURE_MODE
    cite_chunk  = remaining[cursor:cursor + N_PER_FAILURE_MODE]; cursor += N_PER_FAILURE_MODE
    contra_chunk = remaining[cursor:cursor + N_PER_FAILURE_MODE]; cursor += N_PER_FAILURE_MODE
    print(f"      unsupported_claim chunk:           {len(unsup_chunk)}")
    print(f"      unsupported_numerical_claim chunk: {len(num_chunk)} (all fabricated)")
    print(f"      hallucinated_citation chunk:       {len(cite_chunk)}")
    print(f"      contradiction chunk:               {len(contra_chunk)}")

    # ---- Build samples ---------------------------------------------------
    print("[4/6] Building eval samples...")
    eval_samples = []
    next_id = 0

    # Trustworthy
    for ex in trust_chunk:
        eval_samples.append(make_trustworthy(ex, next_id))
        next_id += 1

    # Mode 1: unsupported_claim
    for ex in unsup_chunk:
        s = make_untrustworthy(ex, next_id, "unsupported_claim",
                               inject_unsupported_claim, rng)
        if s is not None:
            eval_samples.append(s); next_id += 1

    # Mode 2: unsupported_numerical_claim — all fabricated_percentage
    # See decisions.md D2.11 for why we dropped the modified_existing_number sub-type.
    for ex in num_chunk:
        s = make_untrustworthy(
            ex, next_id, "unsupported_numerical_claim",
            inject_unsupported_numerical_claim, rng,
            poisoner_kwargs={"prefer_modify": False},
        )
        if s is not None:
            eval_samples.append(s); next_id += 1

    # Mode 3: hallucinated_citation
    for ex in cite_chunk:
        s = make_untrustworthy(ex, next_id, "hallucinated_citation",
                               inject_hallucinated_citation, rng)
        if s is not None:
            eval_samples.append(s); next_id += 1

    # Mode 4: contradiction
    for ex in contra_chunk:
        s = make_untrustworthy(ex, next_id, "contradiction",
                               inject_contradiction, rng)
        if s is not None:
            eval_samples.append(s); next_id += 1

    print(f"      Built {len(eval_samples)} samples.")

    # ---- Disjointness sanity check ---------------------------------------
    print("[5/6] Verifying pool disjointness (no pubid collisions)...")
    pubids_by_label = {"trustworthy": set(), "untrustworthy": set()}
    for s in eval_samples:
        pubids_by_label[s["label"]].add(s["pubid"])
    overlap = pubids_by_label["trustworthy"] & pubids_by_label["untrustworthy"]
    if overlap:
        raise RuntimeError(f"Pool leakage! {len(overlap)} pubids in both pools: {list(overlap)[:5]}")
    print(f"      OK: {len(pubids_by_label['trustworthy'])} unique trustworthy pubids, "
          f"{len(pubids_by_label['untrustworthy'])} unique untrustworthy pubids, "
          f"0 overlap.")

    # ---- Write eval_set.jsonl --------------------------------------------
    print("[6/6] Writing files...")
    os.makedirs(os.path.dirname(EVAL_PATH), exist_ok=True)
    with open(EVAL_PATH, "w") as f:
        for s in eval_samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"      -> {EVAL_PATH}")

    # ---- Write corpus.jsonl ---------------------------------------------
    seen = set()
    n_passages = 0
    with open(CORPUS_PATH, "w") as f:
        for ex in examples:
            for passage in ex["context"]["contexts"]:
                key = passage[:200]
                if key in seen:
                    continue
                seen.add(key)
                record = {"pubid": ex["pubid"], "passage": passage}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                n_passages += 1
    print(f"      -> {CORPUS_PATH}  ({n_passages} unique passages)")

    # ---- Summary ---------------------------------------------------------
    print()
    print("=" * 60)
    print("Eval Set Summary")
    print("=" * 60)
    label_counts = Counter(s["label"] for s in eval_samples)
    print(f"Total samples: {len(eval_samples)}")
    for k, v in label_counts.most_common():
        print(f"  {k}: {v}")
    print()

    print("By failure mode:")
    fm_counts = Counter(s["failure_mode"] for s in eval_samples)
    for k, v in fm_counts.most_common():
        print(f"  {k}: {v}")
    print()

    print("Numerical sub-types (all fabricated; modified dropped per D2.11):")
    num_subtypes = Counter(
        s["metadata"].get("numerical_subtype")
        for s in eval_samples
        if s["failure_mode"] == "unsupported_numerical_claim"
    )
    for k, v in num_subtypes.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
