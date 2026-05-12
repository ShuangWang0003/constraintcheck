"""
Agent: LangGraph-based pipeline for auditing LLM-generated answers.

Pipeline: extract → retrieve → verify → aggregate

Aggregation rules (from Day 1 design):
  - reliability_score = supported_claims / total_claims
  - if any CONTRADICTED → untrustworthy
  - elif reliability_score < 0.7 → untrustworthy
  - else → trustworthy
"""

import json
from typing import TypedDict

from langgraph.graph import StateGraph, END

from src.claim_extractor import extract_claims
from src.retriever import retrieve
from src.verifier import verify


# =========================================================================
# State
# =========================================================================
class AuditState(TypedDict):
    question: str
    answer: str
    claims: list[str]
    evidences: list[list[str]]
    verdicts: list[dict]
    reliability_score: float
    prediction: str
    failure_modes: list[str]


# =========================================================================
# Nodes
# =========================================================================
def extract_node(state: AuditState) -> AuditState:
    state["claims"] = extract_claims(state["answer"])
    return state


def retrieve_node(state: AuditState) -> AuditState:
    state["evidences"] = [
        retrieve(claim, top_k=3)
        for claim in state["claims"]
    ]
    return state


def verify_node(state: AuditState) -> AuditState:
    state["verdicts"] = [
        verify(claim, evidence)
        for claim, evidence in zip(state["claims"], state["evidences"])
    ]
    return state


def aggregate_node(state: AuditState) -> AuditState:
    verdicts = state["verdicts"]

    if not verdicts:
        state["reliability_score"] = 0.0
        state["prediction"] = "untrustworthy"
        state["failure_modes"] = ["no_claims_extracted"]
        return state

    supported = sum(1 for v in verdicts if v["verdict"] == "SUPPORTED")
    contradicted = any(v["verdict"] == "CONTRADICTED" for v in verdicts)
    reliability_score = supported / len(verdicts)

    if contradicted:
        prediction = "untrustworthy"
    elif reliability_score < 0.7:
        prediction = "untrustworthy"
    else:
        prediction = "trustworthy"

    # Failure mode tagging
    failure_modes = []
    for v in verdicts:
        if v["verdict"] == "CONTRADICTED":
            failure_modes.append("contradiction")
        elif v["verdict"] == "UNSUPPORTED":
            failure_modes.append("unsupported_claim")

    state["reliability_score"] = round(reliability_score, 3)
    state["prediction"] = prediction
    state["failure_modes"] = list(set(failure_modes))
    return state


# =========================================================================
# Graph
# =========================================================================
def build_agent():
    graph = StateGraph(AuditState)
    graph.add_node("extract", extract_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("verify", verify_node)
    graph.add_node("aggregate", aggregate_node)

    graph.set_entry_point("extract")
    graph.add_edge("extract", "retrieve")
    graph.add_edge("retrieve", "verify")
    graph.add_edge("verify", "aggregate")
    graph.add_edge("aggregate", END)

    return graph.compile()


# Module-level singleton
_agent = None

def get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


def audit(question: str, answer: str) -> dict:
    """Main entry point. Returns full audit result as dict."""
    agent = get_agent()
    result = agent.invoke({
        "question": question,
        "answer": answer,
        "claims": [],
        "evidences": [],
        "verdicts": [],
        "reliability_score": 0.0,
        "prediction": "",
        "failure_modes": [],
    })
    return dict(result)


# =========================================================================
# Smoke test
# =========================================================================
if __name__ == "__main__":
    import json

    question = "Does aspirin reduce heart attack risk?"
    answer = (
        "Aspirin reduces heart attack risk in patients with cardiovascular disease. "
        "This effect has been demonstrated in multiple randomized controlled trials. "
        "This was first reported by researchers at MIT in 2019."
    )

    print("=" * 70)
    print("Agent smoke test")
    print("=" * 70)
    print(f"Question: {question}")
    print(f"Answer:   {answer}")
    print()

    result = audit(question, answer)

    print("Claims extracted:")
    for i, claim in enumerate(result["claims"], 1):
        verdict = result["verdicts"][i-1] if i <= len(result["verdicts"]) else {}
        print(f"  [{i}] {claim}")
        print(f"       → {verdict.get('verdict', '?')} | {verdict.get('reasoning', '')[:80]}")

    print()
    print(f"Reliability score: {result['reliability_score']}")
    print(f"Prediction:        {result['prediction']}")
    print(f"Failure modes:     {result['failure_modes']}")
    print()
    print("Full JSON:")
    print(json.dumps(result, indent=2))
