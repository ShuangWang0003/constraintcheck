"""
Claim extractor: splits answer text into individual verifiable claims.

Day 3: NLTK Punkt sentence tokenizer replacing period-split mock.
Day 7 fix: filter out metadata sentences (trial registration, ClinicalTrials,
NCT numbers) that cannot be grounded in evidence and artificially lower
reliability scores.
"""

import re
import nltk

# Download punkt if needed
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt")

try:
    nltk.data.find("tokenizers/punkt_tab")
except LookupError:
    nltk.download("punkt_tab")


# Patterns for sentences that are metadata, not verifiable claims
_METADATA_PATTERNS = [
    r"ClinicalTrials\.gov",
    r"\bNCT\d{5,}\b",
    r"\bISRCTN\d+\b",
    r"Trial [Rr]egistration",
    r"[Cc]linical [Tt]rial [Nn]umber",
    r"^\s*\(?[A-Z][a-z]+ et al\.\,?\s*\d{4}\)?\.?\s*$",  # bare citations
]

_METADATA_RE = re.compile("|".join(_METADATA_PATTERNS))


def extract_claims(answer: str) -> list[str]:
    """
    Split answer into verifiable claim sentences.

    Filters:
    - Sentences shorter than 4 words
    - Metadata sentences (trial registration numbers, bare citations)
    """
    if not answer or not answer.strip():
        return []

    sentences = nltk.sent_tokenize(answer)

    claims = []
    for s in sentences:
        s = s.strip()
        # Filter: too short
        if len(s.split()) < 4:
            continue
        # Filter: metadata / registration sentences
        if _METADATA_RE.search(s):
            continue
        claims.append(s)

    return claims


if __name__ == "__main__":
    test_cases = [
        # Normal answer
        "Aspirin reduces heart attack risk. This was shown in multiple RCTs.",
        # Contains NCT number — should be filtered
        "Trial Registration (ORIGIN ClinicalTrials.gov number NCT00069784).",
        # Contains both
        "Severe hypoglycaemia increases CV risk. Trial Registration NCT00069784.",
    ]
    for text in test_cases:
        claims = extract_claims(text)
        print(f"INPUT:  {text[:80]}")
        print(f"CLAIMS: {claims}")
        print()
