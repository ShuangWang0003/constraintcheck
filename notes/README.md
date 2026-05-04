# 🔍 ConstraintCheck

**Local tool for auditing LLM-generated medical answers.**  
Detects hallucinated citations, fabricated statistics, unsupported claims, and contradictions — sentence by sentence — using retrieval-grounded verification with Mistral-7B.

---

## Problem

LLMs frequently hallucinate in medical QA: fabricating citations, inventing statistics, or asserting conclusions unsupported by evidence. Existing approaches rely on black-box confidence scores or human review.

ConstraintCheck provides an interpretable, evidence-grounded audit trail at the sentence level.

---

## Architecture

```text
Input: Question + LLM Answer
        │
        ▼
┌─────────────────────┐
│  Claim Extraction   │  NLTK Punkt sentence tokenizer
│  claim_extractor    │  Filters metadata/registration sentences
└────────┬────────────┘
         │ claims[]
         ▼
┌─────────────────────┐
│     Retrieval       │  FAISS IndexFlatIP over 3,347 PubMedQA
│     retriever       │  passages, all-MiniLM-L6-v2 embeddings
└────────┬────────────┘
         │ evidence[][]
         ▼
┌─────────────────────┐
│    Verification     │  Mistral-7B-Instruct-v0.3
│     verifier        │  V4 prompt with numerical + citation rules
└────────┬────────────┘
         │ verdicts[]
         ▼
┌─────────────────────┐
│    Aggregation      │  reliability_score = supported / total
│      agent          │  CONTRADICTED → untrustworthy
└────────┬────────────┘  score < 0.7 → untrustworthy
         │
         ▼
Output: JSON + Streamlit UI
```

Pipeline orchestrated with **LangGraph StateGraph**.

---

## Key Results

Evaluated on a 200-sample stratified PubMedQA eval set: 100 trustworthy answers and 100 untrustworthy answers across 4 synthetic failure modes.

| Metric | Value |
|---|---:|
| Accuracy | 56.5% |
| Recall, untrustworthy detection | **96.0%** |
| Precision | 53.6% |
| F1 | 68.8% |
| False Positive Rate | 83.0% |

The system prioritizes recall: 96 of 100 untrustworthy answers were correctly flagged.

High FPR is driven by retrieval failing to ground recommendation/conclusion sentences in trustworthy answers.

---

## Failure Mode Detection

| Failure Mode | Detection Rate |
|---|---:|
| Contradiction | 25/25, 100% |
| Unsupported claim | 24/25, 96% |
| Unsupported numerical claim | 24/25, 96% |
| Hallucinated citation | 23/25, 92% |

---

## Ablation Study

| Configuration | Accuracy | Recall | FPR | Latency |
|---|---:|---:|---:|---:|
| Claim-only, no retrieval | 80.0% | 100.0% | 100.0% | 1.5s |
| **+ Retrieval, V2** | **82.0%** | **97.5%** | **80.0%** | **3.2s** |
| + Self-consistency | 80.0% | 100.0% | 100.0% | 7.3s |
| Full system, V4 | 80.0% | 92.5% | 70.0% | 17.0s |

Retrieval grounding is the only component with a clear positive contribution. Self-consistency without retrieval provides no benefit because consensus of wrong answers is still wrong.

---

## How to Run

### 1. Install dependencies

```bash
conda activate xr_agent
pip install -r requirements.txt
```

### 2. Build retrieval index

First time only:

```bash
python -m src.retriever
```

### 3. Run Streamlit demo

```bash
streamlit run app.py
```

Open:

```text
http://localhost:8501
```

**Requirements**: RTX 4090 24GB or equivalent GPU with at least 16GB VRAM.  
Mistral-7B-Instruct-v0.3 is loaded in fp16, approximately 14.5GB.

---

## Evaluation

```bash
# Full 200-sample baseline
python -m experiments.exp1_baseline
python -m experiments.exp1_analyze

# Failure mode breakdown
python -m experiments.exp2_failure_modes

# Ablation study
python -m experiments.exp3_ablation
```

---

## Tech Stack

| Component | Technology |
|---|---|
| LLM | Mistral-7B-Instruct-v0.3, fp16 |
| Pipeline | LangGraph StateGraph |
| Retrieval | FAISS + sentence-transformers, all-MiniLM-L6-v2 |
| Claim extraction | NLTK Punkt |
| Eval dataset | PubMedQA, pqa_labeled |
| Demo | Streamlit |
| Hardware | NVIDIA RTX 4090 24GB |

---

## Limitations & Next Steps

1. **High FPR, 83%**  
   Root cause is retrieval returning cross-study evidence that conflicts with trustworthy claims.  
   Fix: scope retrieval to source-paper contexts rather than a global corpus.

2. **Generic contradiction templates**  
   Poisoned contradiction sentences lack medical vocabulary, so retrieval returns unrelated passages and the verifier defaults to UNSUPPORTED rather than CONTRADICTED.  
   Fix: use medically specific contradiction templates.

3. **Citation dilution in long answers**  
   A hallucinated citation in a 5-claim answer only costs 0.2 reliability points, which may be insufficient to trigger the threshold.  
   Fix: add a dedicated aggregation rule for citation-format UNSUPPORTED verdicts.

4. **Numerical grounding gap**  
   V4 prompt's exact-number rule can fail when retrieved evidence contains percentage figures in a different context.  
   Fix: post-processing regex to verify that exact percentages appear verbatim in evidence.

5. **Domain-specific retrieval**  
   all-MiniLM-L6-v2 is a general-purpose embedding model.  
   Fix: evaluate a medical-domain embedding model such as S-PubMedBERT.

---

## Project Structure

```text
constraintcheck/
├── app.py                          # Streamlit demo
├── src/
│   ├── claim_extractor.py          # NLTK sentence tokenizer
│   ├── retriever.py                # FAISS + sentence-transformers
│   ├── verifier.py                 # Mistral-7B verifier, V4 prompt
│   └── agent.py                    # LangGraph pipeline
├── experiments/
│   ├── exp1_baseline.py            # Full 200-sample evaluation
│   ├── exp2_failure_modes.py       # Per-mode breakdown
│   └── exp3_ablation.py            # Verifier ablation
├── results/                        # Experiment outputs
├── reports/
│   └── failure_cases.md            # 5 failure case studies
├── data/
│   └── eval_set.jsonl              # 200-sample eval set
└── notes/
    └── decisions.md                # Design decision log
```
