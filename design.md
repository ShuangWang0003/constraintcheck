
# ConstraintCheck — Design

## What this project does

ConstraintCheck is a local LLM reliability auditing agent.

Given a question and an LLM-generated answer, the system determines which parts of the answer are likely trustworthy and which may be hallucinated.

The goal is to move beyond simple chatbot generation and instead provide an evidence-grounded reliability assessment.

---

## Inputs and Outputs

### Input

- `question`: the original user question
- `answer`: the LLM-generated answer to audit

### Output (JSON)

```json
{
  "question": "...",
  "answer": "...",
  "claims": [
    {
      "claim": "...",
      "evidence": ["..."],
      "verdict": "SUPPORTED | UNSUPPORTED | CONTRADICTED",
      "reasoning": "..."
    }
  ],
  "reliability_score": 0.0,
  "prediction": "trustworthy | untrustworthy",
  "failure_modes": ["..."]
}
