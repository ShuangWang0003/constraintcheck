"""
Verifier: given a claim and retrieved evidence, decide if the claim is supported.

Day 1 (mock): returns random verdicts for pipeline testing.
Day 5 (real): replaced with Mistral-7B-Instruct-v0.3 verifier with structured prompt.
"""

import random


def verify(claim: str, evidence: list[str]) -> dict:
    """
    Mock verifier: randomly picks a verdict.
    
    Returns:
        {
            "verdict": "SUPPORTED" | "UNSUPPORTED" | "CONTRADICTED",
            "reasoning": str
        }
    """
    verdict = random.choice(["SUPPORTED", "UNSUPPORTED", "CONTRADICTED"])
    return {
        "verdict": verdict,
        "reasoning": f"[Mock reasoning for verdict={verdict}]",
    }


if __name__ == "__main__":
    random.seed(42)  # reproducible test output

    test_claim = "Aspirin reduces heart attack risk by 22 percent"
    test_evidence = [
        "Mock evidence about aspirin and cardiovascular health.",
        "Mock evidence about clinical trials.",
    ]
    result = verify(test_claim, test_evidence)
    print(f"Claim:    {test_claim}")
    print(f"Verdict:  {result['verdict']}")
    print(f"Reason:   {result['reasoning']}")
