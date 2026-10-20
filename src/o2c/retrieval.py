from pathlib import Path
import os
import numpy as np

class EvidenceRetriever:
    """Semantic retrieval with FAISS; lexical fallback is available for constrained environments."""
    def __init__(self, chunks, mode=None, model_name=None):
        self.chunks = chunks
        self.mode = (mode or os.getenv("RETRIEVAL_MODE", "semantic")).lower()
        self.index = None
        self.model = None
        self.matrix = None
        if self.mode == "semantic":
            try:
                from sentence_transformers import SentenceTransformer
                import faiss
                self.faiss = faiss
                self.model = SentenceTransformer(model_name or os.getenv(
                    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
                vectors = self.model.encode(chunks, convert_to_numpy=True, normalize_embeddings=True)
                self.matrix = np.asarray(vectors, dtype="float32")
                self.index = faiss.IndexFlatIP(self.matrix.shape[1])
                self.index.add(self.matrix)
            except Exception:
                # Network/model-download issues should not prevent API startup.
                self.mode = "lexical"

    def search(self, query, k=4):
        if not self.chunks:
            return []
        k = min(max(int(k), 1), len(self.chunks))
        if self.mode == "semantic" and self.index is not None:
            q = self.model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
            scores, ids = self.index.search(np.asarray(q, dtype="float32"), k)
            return [{"text": self.chunks[int(i)], "score": float(s)}
                    for s, i in zip(scores[0], ids[0]) if int(i) >= 0]
        terms = set(query.lower().split())
        ranked = []
        for chunk in self.chunks:
            words = set(chunk.lower().split())
            score = len(terms & words) / max(1, len(terms))
            ranked.append({"text": chunk, "score": score})
        return sorted(ranked, key=lambda x: x["score"], reverse=True)[:k]
