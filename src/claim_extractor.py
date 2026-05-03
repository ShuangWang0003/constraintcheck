"""
Claim Extractor: splits an LLM-generated answer into a list of claims.

Day 3 (real): NLTK Punkt sentence tokenizer.
  - Handles abbreviations correctly: "Dr.", "Fig.", "i.e.", "e.g.", "vs."
  - Handles decimal numbers: "5.7%", "p=0.05"
  - Handles citation references: "(Smith et al., 2020)"

The interface (extract_claims(answer: str) -> list[str]) is unchanged
from the Day 1 mock, so agent.py needs no modification.
"""

import nltk

# Filter out very short fragments (likely citation tails or truncated stubs)
MIN_CLAIM_WORDS = 4


def extract_claims(answer: str) -> list[str]:
    """
    Split an answer into sentence-level claims.

    Args:
        answer: the LLM-generated answer to audit

    Returns:
        A list of claim strings, each at least MIN_CLAIM_WORDS words long.
        Empty list if the answer has no extractable claims.
    """
    if not answer or not answer.strip():
        return []

    sentences = nltk.sent_tokenize(answer)
    claims = [s.strip() for s in sentences if len(s.strip().split()) >= MIN_CLAIM_WORDS]
    return claims


if __name__ == "__main__":
    # Quick smoke test on a real-looking medical answer with abbreviations
    test_answer = (
        "Aspirin reduces heart attack risk by 22 percent (Smith et al., 2018). "
        "This was confirmed in a 2018 meta-analysis. "
        "Dr. Johnson's review found similar effects across age groups. "
        "However, the benefit may not extend to patients over 70 years."
    )
    claims = extract_claims(test_answer)
    print(f"Found {len(claims)} claims:")
    for i, c in enumerate(claims, 1):
        print(f"  {i}. {c}")
