"""Embedding service.

An *embedding* turns text into a list of numbers (a vector) so that texts with
similar MEANING end up close together. all-MiniLM-L6-v2 produces 384 numbers
per text. Vectors are L2-normalised, so cosine similarity == dot product.

`SentenceTransformerEmbedder` is the real model used by the app.
`HashingEmbedder` is a tiny deterministic stand-in used ONLY by automated
tests (no 90 MB download); it captures word overlap, not meaning.
"""
from __future__ import annotations

import hashlib
import os
import re
import threading
import time
from typing import Protocol

import numpy as np

from app.core.logging import get_logger

log = get_logger("embeddings")


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> np.ndarray: ...


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """cos(a, b) = a·b / (|a|·|b|). 1 = same direction (same meaning), 0 = unrelated."""
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, cache_dir: str):
        self.name = model_name
        self.dim = 384
        self._cache_dir = cache_dir
        self._model = None
        self._lock = threading.Lock()
        self.load_error: str | None = None
        self.load_seconds: float | None = None

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def _load(self):
        with self._lock:
            if self._model is None:
                t0 = time.perf_counter()
                os.environ.setdefault("HF_HOME", self._cache_dir)
                os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
                from sentence_transformers import SentenceTransformer
                try:
                    self._model = SentenceTransformer(self.name, cache_folder=self._cache_dir, device="cpu")
                    get_dim = getattr(self._model, "get_embedding_dimension", None) or self._model.get_sentence_embedding_dimension
                    self.dim = int(get_dim() or 384)
                    self.load_error = None
                    self.load_seconds = round(time.perf_counter() - t0, 2)
                    log.info("Embedding model loaded in %.1fs (dim=%d)", self.load_seconds, self.dim)
                except Exception as exc:  # network down on first run, corrupt cache, ...
                    self.load_error = f"{type(exc).__name__}: {exc}"[:300]
                    raise
        return self._model

    def warm_up(self) -> None:
        try:
            self._load()
        except Exception:
            log.warning("Embedding model could not be loaded: %s", self.load_error)

    def embed(self, texts: list[str]) -> np.ndarray:
        model = self._load()
        vecs = model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)


class HashingEmbedder:
    """TEST-ONLY deterministic embedder (feature hashing of words + word bigrams)."""

    def __init__(self, dim: int = 384):
        self.name = "test-hashing-embedder"
        self.dim = dim
        self.loaded = True
        self.load_error = None
        self.load_seconds = 0.0

    def warm_up(self) -> None:  # pragma: no cover - nothing to do
        pass

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            words = re.findall(r"[a-z0-9]+", t.lower())
            feats = words + [f"{a}_{b}" for a, b in zip(words, words[1:])]
            for f in feats:
                h = int(hashlib.md5(f.encode()).hexdigest(), 16)
                out[i, h % self.dim] += 1.0 if (h >> 8) % 2 else -1.0
            n = np.linalg.norm(out[i])
            if n:
                out[i] /= n
        return out


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        from app.core.config import get_settings
        s = get_settings()
        _embedder = SentenceTransformerEmbedder(s.embedding_model, str(s.resolve(s.models_cache_path)))
    return _embedder


def set_embedder(embedder: Embedder | None) -> None:
    """Used by tests to inject the HashingEmbedder."""
    global _embedder
    _embedder = embedder
