"""ChromaDB wrapper.

Two collections, both using cosine distance:
  doc_chunks   - one vector per document chunk
  query_cache  - one vector per cached question (semantic cache)

We always pass our own embeddings (embedding_function=None) so Chroma never
downloads a second model. Chroma reports cosine *distance* = 1 - similarity.
"""
from __future__ import annotations

import threading
from typing import Any

import numpy as np

from app.core.logging import get_logger

log = get_logger("vector_store")
DOC_COLLECTION = "doc_chunks"
CACHE_COLLECTION = "query_cache"


class VectorStore:
    def __init__(self, path: str | None):
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        cs = ChromaSettings(anonymized_telemetry=False, allow_reset=True)
        self._client = chromadb.PersistentClient(path=path, settings=cs) if path else chromadb.EphemeralClient(settings=cs)
        self._lock = threading.Lock()
        self.docs = self._collection(DOC_COLLECTION)
        self.cache = self._collection(CACHE_COLLECTION)

    def _collection(self, name: str):
        return self._client.get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine"}, embedding_function=None)

    # ------------------------------------------------------------ generic helpers
    def add(self, coll, ids: list[str], vectors: np.ndarray, metadatas: list[dict], documents: list[str] | None = None):
        if not ids:
            return
        with self._lock:
            for i in range(0, len(ids), 500):   # Chroma has a max batch size
                coll.upsert(ids=ids[i:i + 500], embeddings=vectors[i:i + 500].tolist(),
                            metadatas=metadatas[i:i + 500],
                            documents=documents[i:i + 500] if documents else None)

    def delete(self, coll, ids: list[str] | None = None, where: dict | None = None):
        with self._lock:
            if ids:
                coll.delete(ids=ids)
            elif where:
                coll.delete(where=where)

    def query(self, coll, vector: np.ndarray, k: int, where: dict) -> list[dict[str, Any]]:
        """Nearest neighbours restricted by `where` (tenant / document filters ALWAYS applied)."""
        if coll.count() == 0:
            return []
        res = coll.query(query_embeddings=[vector.tolist()], n_results=k, where=where,
                         include=["metadatas", "distances", "embeddings"])
        out = []
        for i, vid in enumerate(res["ids"][0]):
            emb = np.asarray(res["embeddings"][0][i], dtype=np.float32)
            sim = float(np.dot(emb, vector) / ((np.linalg.norm(emb) * np.linalg.norm(vector)) or 1.0))
            out.append({"id": vid, "metadata": res["metadatas"][0][i], "similarity": sim,
                        "distance": float(res["distances"][0][i])})
        return out

    def count(self) -> dict[str, int]:
        return {"doc_chunks": self.docs.count(), "query_cache": self.cache.count()}


_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        from app.core.config import get_settings
        s = get_settings()
        _store = VectorStore(str(s.resolve(s.chroma_path)))
    return _store


def set_vector_store(store: VectorStore | None) -> None:
    global _store
    _store = store
