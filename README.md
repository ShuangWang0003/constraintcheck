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



## Status

🚧 Active development (Day 4 of 14-day build complete)

**Day 1 ✅**: Project skeleton, mock pipeline, 7/7 tests passing.

**Day 2 ✅**: Built 200-pair evaluation set from PubMedQA with synthetically poisoned variants spanning four failure modes (unsupported claim, unsupported numerical claim, hallucinated citation, contradiction). Includes runtime disjointness assertions between trustworthy/untrustworthy pools, reproducible seeded sampling, and a full manual inspection pass that surfaced a domain-specific limitation (see `notes/decisions.md` D2.10–D2.11).

**Day 3 ✅**: Replaced mock period-based sentence splitter with NLTK Punkt tokenizer. Added 10 unit tests; quantitative comparison on 200 samples showed mock breaks medical abbreviations like `vs.` and URLs like `ClinicalTrials.gov` into invalid fragments — NLTK correctly preserves them.

**Day 4 ✅**: Replaced mock retriever with FAISS + sentence-transformers (all-MiniLM-L6-v2) over 3347 PubMedQA passages. Disk-cached index for sub-2s load times across re-runs. Manual inspection on 5 eval samples surfaced four research-relevant retrieval behaviors per failure mode — most notably, that NLTK's sentence boundaries naturally isolate hallucinated citations as standalone claims, leading to high-quality UNSUPPORTED retrieval signals (see `notes/decisions.md` D4.1).

## Day 5 — In Progress

### D5.0 — Mistral-7B-v0.3 load + inference verified on RTX 4090

**Verified**:
- Model loads in ~5s from HuggingFace cache (warm load)
- GPU memory: 14.5 GB / 24 GB (fp16, no quantization needed)
- Inference latency: ~1s per sample (3 sanity prompts)
- Format compliance: trivial prompt produces "Verdict: SUPPORTED" exactly
- Verdict accuracy on 2 realistic test cases (1 SUPPORTED + 1 UNSUPPORTED): 2/2 correct
- Reasoning quality: model identifies specific evidence-claim mismatches (e.g., "evidence is a 2018 meta-analysis, not a finding from MIT in 2019")

**Decision**: Proceed with full prompt design and 50-sample evaluation tomorrow.
