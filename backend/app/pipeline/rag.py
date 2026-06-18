import json
from pathlib import Path

from backend.app.config import settings


class SrkiRetriever:
    def __init__(self) -> None:
        self.encoder: SentenceTransformer | None = None
        self.index: faiss.Index | None = None
        self.documents: list[dict] = []
        self._load()

    def _load(self) -> None:
        index_dir = settings.rag_index_dir
        meta_path = index_dir / "documents.json"
        index_path = index_dir / "faiss.index"
        if not meta_path.exists() or not index_path.exists():
            return
        try:
            import faiss
            from sentence_transformers import SentenceTransformer
        except ImportError:
            return
        with open(meta_path, encoding="utf-8") as f:
            self.documents = json.load(f)
        self.index = faiss.read_index(str(index_path))
        self.encoder = SentenceTransformer(settings.embedding_model)

    @property
    def ready(self) -> bool:
        return self.index is not None and self.encoder is not None and len(self.documents) > 0

    def search(self, query: str, intent: str | None = None, k: int = 3) -> list[dict]:
        if not self.ready:
            return []
        import numpy as np

        q_emb = self.encoder.encode([query], normalize_embeddings=True)
        q_emb = np.asarray(q_emb, dtype=np.float32)
        scores, indices = self.index.search(q_emb, k)
        hits: list[dict] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.documents):
                continue
            doc = dict(self.documents[idx])
            if intent and doc.get("intent") and doc["intent"] != intent:
                continue
            doc["score"] = float(score)
            hits.append(doc)
        if not hits and intent:
            for doc in self.documents:
                if doc.get("intent") == intent:
                    hits.append({**doc, "score": 0.0})
                    if len(hits) >= k:
                        break
        return hits
