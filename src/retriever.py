"""
Retriever: given a claim, return relevant evidence passages from the corpus.

Day 4 (real): FAISS + sentence-transformers over PubMedQA contexts.
  - Embedding model: all-MiniLM-L6-v2 (22MB, fast, generic baseline)
  - Index type: FAISS IndexFlatIP with L2-normalized embeddings = cosine similarity
  - Caches built index to disk so subsequent loads are < 2 seconds.

Interface:
  retrieve(claim: str, top_k: int = 3) -> list[str]
    Returns top_k passage strings, ranked by cosine similarity.

This is the same interface as the Day 1 mock — agent.py needs no change.
"""

import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

CORPUS_PATH = "data/corpus.jsonl"
INDEX_PATH = "data/faiss.index"
PASSAGES_PATH = "data/corpus_passages.npy"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class Retriever:
    """FAISS-based dense retriever over PubMedQA contexts."""

    def __init__(self, corpus_path: str = CORPUS_PATH):
        self.corpus_path = corpus_path
        self.model = None      # lazy
        self.passages = None   # lazy
        self.index = None      # lazy

    def _ensure_loaded(self):
        """Load model + corpus + index on first use (lazy initialization)."""
        if self.index is not None:
            return  # already loaded

        # Load embedding model (downloads on first use, ~90MB)
        print(f"[Retriever] Loading embedding model: {EMBEDDING_MODEL}")
        self.model = SentenceTransformer(EMBEDDING_MODEL)

        # Try cached index first
        if os.path.exists(INDEX_PATH) and os.path.exists(PASSAGES_PATH):
            print(f"[Retriever] Loading cached index from {INDEX_PATH}")
            self.index = faiss.read_index(INDEX_PATH)
            self.passages = np.load(PASSAGES_PATH, allow_pickle=True).tolist()
            print(f"[Retriever] Cached index loaded: {len(self.passages)} passages")
        else:
            print(f"[Retriever] Building index from scratch...")
            self._build_index()

    def _build_index(self):
        """Encode all corpus passages and build FAISS index."""
        # Load corpus
        passages = []
        with open(self.corpus_path) as f:
            for line in f:
                rec = json.loads(line)
                passages.append(rec["passage"])
        print(f"[Retriever] Loaded {len(passages)} passages from {self.corpus_path}")

        # Encode passages
        print(f"[Retriever] Encoding passages (this takes ~30-60s)...")
        embeddings = self.model.encode(
            passages,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2-normalize so IP == cosine similarity
        ).astype("float32")

        # Build FAISS index (Inner Product on normalized = cosine)
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings)
        self.passages = passages

        # Cache to disk
        os.makedirs(os.path.dirname(INDEX_PATH) or ".", exist_ok=True)
        faiss.write_index(self.index, INDEX_PATH)
        np.save(PASSAGES_PATH, np.array(self.passages, dtype=object))
        print(f"[Retriever] Index saved: {INDEX_PATH}")

    def retrieve(self, claim: str, top_k: int = 3) -> list[str]:
        """Return the top_k most relevant passages for a claim."""
        self._ensure_loaded()

        if not claim or not claim.strip():
            return []

        # Encode query (also normalized so IP = cosine)
        q_emb = self.model.encode(
            [claim],
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype("float32")

        # Search
        scores, indices = self.index.search(q_emb, top_k)
        return [self.passages[i] for i in indices[0]]


# -------------------------------------------------------------------------
# Module-level singleton (preserves Day 1 interface for agent.py)
# -------------------------------------------------------------------------
_retriever: Retriever | None = None


def retrieve(claim: str, top_k: int = 3) -> list[str]:
    """Module-level retrieval function. Lazy-loads on first call."""
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever.retrieve(claim, top_k=top_k)


# -------------------------------------------------------------------------
# Smoke test
# -------------------------------------------------------------------------
if __name__ == "__main__":
    test_claims = [
        "Aspirin reduces heart attack risk in patients with cardiovascular disease.",
        "Mitochondria play a role in programmed cell death in plants.",
        "The quick brown fox jumps over the lazy dog.",  # nonsense control
    ]

    for claim in test_claims:
        print("\n" + "=" * 70)
        print(f"CLAIM: {claim}")
        print("=" * 70)
        results = retrieve(claim, top_k=3)
        for i, r in enumerate(results, 1):
            print(f"\n  [{i}] {r[:250]}{'...' if len(r) > 250 else ''}")
