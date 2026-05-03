"""
Agent: end-to-end ConstraintCheck pipeline.

Day 1 (mock): plain Python orchestration with mock modules.
Day 6 (real): refactored into a LangGraph workflow.

Pipeline:
    answer
      -> claim extraction
      -> retrieval grounding (per claim)
      -> verifier (per claim)
      -> aggregation (reliability score, prediction, failure modes)
"""

from src import claim_extractor
from src import retriever
from src import verifier


# --- Aggregation rules ---------------------------------------------------
RELIABILITY_THRESHOLD = 0.7  # below this, the answer is flagged untrustworthy


def _aggregate(claim_results: list[dict]) -> dict:
    """Combine per-claim verdicts into an overall prediction."""
    n_total = len(claim_results)
    if n_total == 0:
        return {
            "reliability_score": 0.0,
            "prediction": "untrustworthy",
            "failure_modes": ["no_claims_extracted"],
        }

    n_supported = sum(1 for r in claim_results if r["verdict"] == "SUPPORTED")
    n_contradicted = sum(1 for r in claim_results if r["verdict"] == "CONTRADICTED")

    reliability_score = n_supported / n_total

    if n_contradicted > 0:
        prediction = "untrustworthy"
    elif reliability_score < RELIABILITY_THRESHOLD:
        prediction = "untrustworthy"
    else:
        prediction = "trustworthy"

    failure_modes = []
    if n_contradicted > 0:
        failure_modes.append("contradiction")
    if any(r["verdict"] == "UNSUPPORTED" for r in claim_results):
        failure_modes.append("unsupported_claim")

    return {
        "reliability_score": round(reliability_score, 3),
        "prediction": prediction,
        "failure_modes": failure_modes,
    }


# --- Main entry point ----------------------------------------------------
def audit(question: str, answer: str, top_k: int = 3) -> dict:
    """Audit an LLM-generated answer end-to-end."""
    claims = claim_extractor.extract_claims(answer)

    claim_results = []
    for claim in claims:
        evidence = retriever.retrieve(claim, top_k=top_k)
        verdict = verifier.verify(claim, evidence)
        claim_results.append({
            "claim": claim,
            "evidence": evidence,
            "verdict": verdict["verdict"],
            "reasoning": verdict["reasoning"],
        })

    aggregation = _aggregate(claim_results)

    return {
        "question": question,
        "answer": answer,
        "claims": claim_results,
        **aggregation,
    }


if __name__ == "__main__":
    import json
    import random
    random.seed(42)

    test_question = "Does aspirin reduce heart attack risk?"
    test_answer = (
        "Aspirin reduces heart attack risk by 22 percent. "
        "This was confirmed in a 2018 meta-analysis. "
        "However, it should not be taken without medical advice."
    )

    result = audit(test_question, test_answer)
    print(json.dumps(result, indent=2))
