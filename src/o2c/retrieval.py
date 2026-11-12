import logging
import os
import re
import numpy as np

logger = logging.getLogger(__name__)

_STOP_WORDS = {
    "a", "an", "and", "are", "do", "does", "for", "how", "is", "list",
    "me", "of", "please", "record", "records", "show", "the", "their",
    "today", "what", "which", "who", "with",
}
_TERM_SYNONYMS = {
    "late": "overdue",
    "unpaid": "overdue",
}


def _lexical_terms(text):
    terms = set()
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        if token in _STOP_WORDS:
            continue
        if len(token) > 4 and token.endswith("ies"):
            token = f"{token[:-3]}y"
        elif len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        token = _TERM_SYNONYMS.get(token, token)
        terms.add(token)
    return terms


class EvidenceRetriever:
    """Semantic retrieval with FAISS; lexical fallback is available for constrained environments."""
    def __init__(self, chunks, mode=None, model_name=None):
        self.chunks = chunks
        self.mode = (mode or os.getenv("RETRIEVAL_MODE", "semantic")).lower()
        if self.mode not in {"semantic", "lexical"}:
            raise ValueError("retrieval mode must be 'semantic' or 'lexical'")
        self.index = None
        self.model = None
        self.matrix = None
        self.fallback_reason = None
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
            except Exception as exc:
                self.fallback_reason = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "Semantic retrieval initialization failed; using lexical retrieval: %s",
                    self.fallback_reason,
                )
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
        terms = _lexical_terms(query)
        if not terms:
            return []

        ranked = []
        for chunk in self.chunks:
            words = _lexical_terms(chunk)
            score = len(terms & words) / max(1, len(terms))
            if score > 0:
                ranked.append({"text": chunk, "score": score})
        if not ranked:
            return []

        ranked.sort(key=lambda item: (-item["score"], item["text"]))
        minimum_score = max(0.5, ranked[0]["score"] * 0.8)
        results = []
        seen_entities = set()
        for item in ranked:
            if item["score"] < minimum_score:
                continue
            entity = tuple(item["text"].split()[:2])
            if entity in seen_entities:
                continue
            seen_entities.add(entity)
            results.append(item)
            if len(results) == k:
                break
        return results
