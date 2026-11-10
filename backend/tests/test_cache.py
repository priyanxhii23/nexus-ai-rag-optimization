"""Semantic cache: exact/semantic hits, threshold, TTL, invalidation, permissions, intent guard."""
from datetime import timedelta

import numpy as np
import pytest

from app.cache.semantic_cache import SemanticCache, intent_conflicts, normalize_query, scope_key
from app.embeddings import cosine_similarity
from app.models import CacheEntry, Document, utcnow
from tests.conftest import ask, upload


def _unit(*vals, dim=384):
    v = np.zeros(dim, dtype=np.float32)
    v[: len(vals)] = vals
    return v / np.linalg.norm(v)


def _store(cache, q, vec, tenant="t", scope="all", versions=None, is_mock=True, ttl=24):
    return cache.store_answer(query=q, vector=vec, tenant=tenant, scope=scope, answer=f"answer to {q}", citations=[],
                              source_versions=versions or {}, model="mock:mock-small", provider="mock",
                              is_mock=is_mock, input_tokens=10, output_tokens=5, cost_usd=0.001, latency_ms=900,
                              ttl_hours=ttl, request_id=None)


def test_cosine_similarity():
    assert cosine_similarity(np.array([1, 0]), np.array([1, 0])) == pytest.approx(1.0)
    assert cosine_similarity(np.array([1, 0]), np.array([0, 1])) == pytest.approx(0.0)
    assert cosine_similarity(np.array([1, 1]), np.array([1, 0])) == pytest.approx(0.7071, abs=1e-4)
    assert cosine_similarity(np.array([0, 0]), np.array([1, 0])) == 0.0


def test_normalisation_and_scope():
    assert normalize_query("  How many DAYS?? ") == "how many days"
    assert scope_key(None) == scope_key([]) == "all"
    assert scope_key([2, 1]) == scope_key([1, 2]) != scope_key([1])


def test_exact_and_semantic_hits_and_threshold(env):
    c = SemanticCache(env.db, env.store)
    _store(c, "How long is the refund window?", _unit(1, 0.0))
    assert c.lookup("how long is the refund window", _unit(1, 0.0), "t", "all", 0.9, True).status == "exact_hit"
    near = c.lookup("What is the length of the refund window?", _unit(1, 0.2), "t", "all", 0.9, True)
    assert near.status == "semantic_hit" and near.similarity == pytest.approx(0.9806, abs=1e-3)
    far = c.lookup("What is the length of the refund window?", _unit(1, 0.6), "t", "all", 0.9, True)
    assert far.status == "miss" and "below threshold" in far.reason


def test_cache_respects_tenant_and_scope(env):
    c = SemanticCache(env.db, env.store)
    _store(c, "How long is the refund window?", _unit(1, 0), tenant="alice", scope="all")
    assert c.lookup("How long is the refund window?", _unit(1, 0), "bob", "all", 0.9, True).status == "miss"
    assert c.lookup("How long is the refund window?", _unit(1, 0), "alice", "docs:x", 0.9, True).status == "miss"


def test_expired_entries_are_not_served(env):
    c = SemanticCache(env.db, env.store)
    e = _store(c, "How long is the refund window?", _unit(1, 0))
    e.expires_at = utcnow() - timedelta(seconds=1)
    env.db.commit()
    r = c.lookup("How long is the refund window?", _unit(1, 0), "t", "all", 0.9, True)
    assert r.status == "miss" and "expired" in r.candidates[0].reasons[0]


def test_changed_or_deleted_or_foreign_source_document_blocks_reuse(env):
    c = SemanticCache(env.db, env.store)
    doc = Document(tenant_id="t", filename="p.txt", content_hash="h", version=1)
    env.db.add(doc)
    env.db.commit()
    _store(c, "How long is the refund window?", _unit(1, 0), versions={str(doc.id): 1})
    assert c.lookup("How long is the refund window?", _unit(1, 0), "t", "all", 0.9, True).hit
    doc.version = 2
    env.db.commit()
    r = c.lookup("How long is the refund window?", _unit(1, 0), "t", "all", 0.9, True)
    assert not r.hit and "changed" in r.reason
    doc.version, doc.tenant_id = 1, "someone-else"
    env.db.commit()
    r = c.lookup("How long is the refund window?", _unit(1, 0), "t", "all", 0.9, True)
    assert not r.hit and "permission" in r.reason
    env.db.delete(doc)
    env.db.commit()
    r = c.lookup("How long is the refund window?", _unit(1, 0), "t", "all", 0.9, True)
    assert not r.hit and "deleted" in r.reason


def test_mock_answers_never_served_in_real_mode(env):
    c = SemanticCache(env.db, env.store)
    _store(c, "How long is the refund window?", _unit(1, 0), is_mock=True)
    r = c.lookup("How long is the refund window?", _unit(1, 0), "t", "all", 0.9, is_mock_mode=False)
    assert not r.hit and "mock" in r.reason


@pytest.mark.parametrize("new,old,reason", [
    ("Which plans do not include phone support?", "Which plans include phone support?", "negation"),
    ("What is the yearly cost of 20 users?", "What is the yearly cost of 10 users?", "numbers"),
    ("Can I get a refund after 30 days?", "Can I get a refund within 30 days?", "qualifier"),
    ("Compare the Pro and Basic plans", "What is the Pro plan?", "intent"),
])
def test_intent_guard(new, old, reason):
    from app.router.query_intelligence import analyze
    problems = intent_conflicts(new, old, analyze(new).category, analyze(old).category)
    assert any(reason in p for p in problems), problems


def test_intent_guard_blocks_high_similarity_semantic_match(env):
    c = SemanticCache(env.db, env.store)
    _store(c, "Can I get a refund within 30 days?", _unit(1, 0))
    r = c.lookup("Can I get a refund after 30 days?", _unit(1, 0.05), "t", "all", 0.9, True)
    assert r.status == "miss" and r.similarity > 0.99 and "qualifier" in r.reason


def test_delete_and_clear(env):
    c = SemanticCache(env.db, env.store)
    e = _store(c, "q one?", _unit(1, 0))
    _store(c, "q two?", _unit(0, 1))
    c.delete_entry(e)
    assert env.db.query(CacheEntry).count() == 1 and env.store.cache.count() == 1
    assert c.clear("t") == 1 and env.store.cache.count() == 0


def test_cache_admin_api(client):
    upload(client)
    ask(client, "How many days to request a refund?")
    hit = ask(client, "How many days to request a refund?")
    assert hit["cache"]["status"] == "exact_hit" and hit["llm_called"] is False
    assert hit["usage"]["input_tokens"] == 0 and hit["cost"]["saved_by_cache_usd"] > 0
    entries = client.get("/api/cache/entries?search=refund").json()
    assert entries["total"] == 1
    eid = entries["entries"][0]["id"]
    detail = client.get(f"/api/cache/entries/{eid}").json()
    assert detail["hit_count"] == 1 and detail["hit_history"][0]["status"] == "exact_hit"
    stats = client.get("/api/cache/stats").json()
    assert stats["active"] == 1 and stats["exact_hits_30d"] == 1
    assert client.delete(f"/api/cache/entries/{eid}").status_code == 200
    assert client.get("/api/cache/entries").json()["total"] == 0
    ask(client, "How many days to request a refund?")
    assert client.delete("/api/cache").json()["deleted"] == 1


def test_cache_can_be_disabled_in_settings(client):
    upload(client)
    client.put("/api/settings", json={"cache_enabled": False})
    ask(client, "How many days to request a refund?")
    assert ask(client, "How many days to request a refund?")["cache"]["status"] == "bypass"


def test_threshold_experiment_endpoint(client):
    d = client.post("/api/cache/threshold-experiment", json={}).json()
    assert 0.85 <= d["recommended_threshold"] <= 0.99
    assert len(d["results"]) == 15 and d["positives"] == 10 and d["negatives"] == 10
    assert all(0 <= r["false_match_rate_with_guard"] <= r["false_match_rate"] for r in d["results"])
