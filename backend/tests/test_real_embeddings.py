"""Checks with the REAL all-MiniLM-L6-v2 model (skipped when it is not downloaded yet)."""
import os

import pytest

from app.core.config import PROJECT_ROOT


def _real_embedder():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from app.embeddings import SentenceTransformerEmbedder
    cache = os.environ.get("MODELS_CACHE_PATH") or str(PROJECT_ROOT / "data" / "models")
    emb = SentenceTransformerEmbedder("sentence-transformers/all-MiniLM-L6-v2", cache)
    try:
        emb.embed(["warm up"])
    except Exception:
        pytest.skip("Embedding model not downloaded yet (run setup_windows.ps1)")
    return emb


@pytest.fixture(scope="module")
def real():
    return _real_embedder()


def test_paraphrases_are_close_and_unrelated_far(real):
    import numpy as np
    v = real.embed(["How many days do customers have to request a refund?",
                    "Within how many days can a customer ask for a refund?",
                    "What is the capital of France?"])
    assert v.shape == (3, 384)
    assert float(np.dot(v[0], v[1])) > 0.85
    assert float(np.dot(v[0], v[2])) < 0.3


def test_threshold_recommendation_is_safe_with_real_model(real):
    from app.evaluation.datasets import load_dataset
    from app.evaluation.threshold import run_threshold_experiment
    d = run_threshold_experiment(load_dataset("nexus_demo_v1")["pairs"], real)
    rec = d["recommended_threshold"]
    row = next(r for r in d["results"] if r["threshold"] >= rec - 1e-9)
    assert rec >= 0.85 and row["false_match_rate_with_guard"] == 0
