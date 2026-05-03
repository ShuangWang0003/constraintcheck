"""
Retriever: given a claim, return relevant evidence passages from a corpus.

Day 1 (mock): returns fixed placeholder strings.
Day 4 (real): replaced with FAISS + sentence-transformers over PubMedQA contexts.
"""


def retrieve(claim: str, top_k: int = 3) -> list[str]:
    """Mock retrieval: returns fake evidence regardless of the claim."""
    return [
        f"[Mock evidence 1 for: '{claim[:40]}...']",
        f"[Mock evidence 2 for: '{claim[:40]}...']",
        f"[Mock evidence 3 for: '{claim[:40]}...']",
    ][:top_k]


if __name__ == "__main__":
    test_claim = "Aspirin reduces heart attack risk by 22 percent"
    evidence = retrieve(test_claim, top_k=3)
    print(f"Retrieved {len(evidence)} evidence passages:")
    for i, e in enumerate(evidence, 1):
        print(f"  {i}. {e}")
