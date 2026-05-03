"""
Claim Extractor: splits an LLM answer into a list of atomic claims.

Day 1 (mock): naive sentence-level splitting using punctuation.
Day 3 (real): replaced with NLTK sent_tokenize.
"""


def extract_claims(answer: str) -> list[str]:
    """Split an answer into claims (sentences)."""
    raw = answer.replace("?", ".").replace("!", ".").split(".")
    claims = [s.strip() for s in raw if len(s.strip().split()) >= 4]
    return claims


if __name__ == "__main__":
    # Quick sanity test
    test_answer = (
        "Aspirin reduces heart attack risk by 22 percent. "
        "This was confirmed in a 2018 meta-analysis. "
        "However, it should not be taken without medical advice."
    )
    claims = extract_claims(test_answer)
    print(f"Found {len(claims)} claims:")
    for i, c in enumerate(claims, 1):
        print(f"  {i}. {c}")
