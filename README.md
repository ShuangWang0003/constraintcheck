# ConstraintCheck

LLM Reliability Auditing Agent — detects hallucinated claims in LLM-generated answers through retrieval grounding and failure-mode analysis.

## Status

Active development: 14-day build.

## Goal

Build a local agent that takes a question and an LLM-generated answer, then produces:

- Reliability score
- Per-claim verdicts: SUPPORTED / UNSUPPORTED / CONTRADICTED
- Retrieved evidence for each claim
- Failure-mode tags: unsupported claim, numerical inconsistency, hallucinated citation, contradiction

## Tech Stack

- Local LLM: Qwen2.5-7B via Ollama
- Embedding: sentence-transformers
- Vector Search: FAISS
- Workflow: LangGraph
- Sentence Splitting: NLTK
- Demo: Streamlit
- Dataset: PubMedQA

## Planned Experiments

1. Overall hallucination detection
2. Failure-mode breakdown
3. Verifier ablation
4. Failure case deep dive

## Project Structure

```text
src/
  claim_extractor.py
  retriever.py
  verifier.py
  agent.py

data/
results/
reports/
experiments/
tests/
