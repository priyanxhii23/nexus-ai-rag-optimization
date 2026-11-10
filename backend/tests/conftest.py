"""Shared test setup.

* Every test gets a brand-new SQLite file and in-memory ChromaDB, so tests
  NEVER touch your real data/nexus.db or data/chroma.
* LLM_MOCK_MODE=true: no paid API calls, ever, during tests.
* A deterministic hashing embedder replaces MiniLM (no 90 MB download).
  Tests marked `real_model` use MiniLM and are skipped if it isn't installed.
"""
import os

os.environ["APP_ENV"] = "test"
os.environ["LLM_MOCK_MODE"] = "true"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["OPENAI_COMPAT_BASE_URL"] = ""
os.environ["MIN_RETRIEVAL_SCORE"] = "0.05"      # hashing embedder gives low scores
os.environ["RATE_LIMIT_PER_MINUTE"] = "10000"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture()
def tmp_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCUMENTS_PATH", str(tmp_path / "documents"))
    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "test.db"))
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture()
def env(tmp_settings):
    """Isolated database + vector store + embedder + registry."""
    from app.database import SessionLocal, configure_engine, init_db
    from app.embeddings import HashingEmbedder, set_embedder
    from app.llm.registry import ModelRegistry, seed_models, set_registry
    from app.rag.vector_store import VectorStore, set_vector_store

    engine = configure_engine(tmp_settings.database_url)
    init_db(engine)
    store, embedder, registry = VectorStore(None), HashingEmbedder(), ModelRegistry(tmp_settings)
    for coll in (store.docs, store.cache):   # EphemeralClient is shared per process - start empty
        ids = coll.get()["ids"]
        if ids:
            coll.delete(ids=ids)
    set_vector_store(store)
    set_embedder(embedder)
    set_registry(registry)
    db = SessionLocal()
    seed_models(db, tmp_settings)

    class Env:
        pass

    e = Env()
    e.db, e.store, e.embedder, e.registry, e.settings, e.engine = db, store, embedder, registry, tmp_settings, engine
    yield e
    db.close()
    set_vector_store(None)
    set_embedder(None)
    set_registry(None)
    engine.dispose()


@pytest.fixture()
def client(env):
    from app.main import app

    app.state.skip_startup = True
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db_session(env):
    return env.db


POLICY = (b"Refund policy. Customers can request a full refund within 30 days of purchase. "
          b"Refunds are paid to the original payment method within 5 business days.\n\n"
          b"Pricing. The Pro plan costs 49 dollars per month and includes priority support. "
          b"The Basic plan costs 19 dollars per month and includes email support only.")


def upload(client, name="policy.txt", data=POLICY, tenant=None):
    headers = {"X-Tenant-ID": tenant} if tenant else {}
    r = client.post("/api/documents", files=[("files", (name, data, "text/plain"))], headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["results"][0]


def ask(client, query, tenant=None, **kw):
    headers = {"X-Tenant-ID": tenant} if tenant else {}
    r = client.post("/api/query", json={"query": query, **kw}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()
