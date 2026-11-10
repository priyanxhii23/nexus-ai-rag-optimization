"""Cost calculation, analytics aggregation, model configuration."""
import pytest

from app.llm.registry import compute_cost
from app.models import ModelConfig
from tests.conftest import ask, upload


def test_claude_list_prices(env):
    cost, status = compute_cost(env.db, "anthropic:claude-opus-5-5", 1_000_000, 1_000_000)
    assert (cost, status) == (24.0, "priced")
    cost, _ = compute_cost(env.db, "anthropic:claude-haiku-5-5", 10_000, 1_000)
    assert cost == pytest.approx(10_000 / 1e6 * 0.10 + 1_000 / 1e6 * 0.50)


def test_long_context_tier(env):
    cost, _ = compute_cost(env.db, "anthropic:claude-haiku-5-5", 200_000, 1_000)
    assert cost == pytest.approx(200_000 / 1e6 * 0.50 + 1_000 / 1e6 * 2.50)


def test_mock_cost_is_simulated_from_real_model(env):
    real, _ = compute_cost(env.db, "anthropic:claude-sonnet-5-5", 500, 100)
    sim, status = compute_cost(env.db, "mock:mock-medium", 500, 100)
    assert status == "simulated" and sim == real


def test_unpriced_models_are_never_given_a_made_up_price(env, client):
    r = client.post("/api/models", json={"provider": "gemini", "model_name": "some-gemini-model", "tier": "small"})
    assert r.status_code == 201
    assert compute_cost(env.db, "gemini:some-gemini-model", 1000, 1000) == (None, "unpriced")
    r = client.patch("/api/models/gemini:some-gemini-model",
                     json={"input_price_per_mtok": 0.5, "output_price_per_mtok": 2.0, "price_source": "ai.google.dev"})
    assert r.status_code == 200
    assert compute_cost(env.db, "gemini:some-gemini-model", 1_000_000, 0) == (0.5, "priced")
    assert env.db.get(ModelConfig, "gemini:some-gemini-model").price_source == "ai.google.dev"
    assert client.patch("/api/models/mock:mock-small", json={"input_price_per_mtok": 1,
                                                             "output_price_per_mtok": 1}).status_code == 422


def test_models_endpoint_explains_availability(client):
    d = client.get("/api/models").json()
    by_id = {m["id"]: m for m in d["models"]}
    assert by_id["mock:mock-small"]["available"] is True
    assert by_id["anthropic:claude-opus-5-5"]["available"] is False
    assert "test mode" in by_id["anthropic:claude-opus-5-5"]["unavailable_reason"]
    client.patch("/api/models/mock:mock-medium", json={"enabled": False})
    assert {m["id"]: m for m in client.get("/api/models").json()["models"]}["mock:mock-medium"]["available"] is False


def test_overview_empty_on_fresh_install(client):
    body = client.get("/api/metrics/overview").json()
    assert body["has_data"] is False and body["total_queries"] == 0
    assert body["cache_hit_rate"] is None and body["avg_latency_ms"] is None
    assert body["recent_activity"] == [] and body["daily"] == []


def test_overview_and_costs_from_real_rows(client):
    upload(client)
    ask(client, "How many days to request a refund?")
    ask(client, "How many days to request a refund?")      # exact hit
    ask(client, "Compare the Pro plan and the Basic plan")  # medium tier
    o = client.get("/api/metrics/overview").json()
    assert o["total_queries"] == 3 and o["llm_calls"] == 2 and o["llm_calls_avoided"] == 1
    assert o["cache_hit_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert o["actual_cost_usd"] == 0 and o["simulated_cost_usd"] > 0     # mock spend is never "actual"
    assert o["saved_by_cache_usd"] > 0
    assert o["small_model_queries"] == 1 and o["medium_model_queries"] == 1
    assert o["daily"][0]["queries"] == 3 and o["recent_routing"]
    c = client.get("/api/metrics/costs").json()
    assert c["is_simulated"] is True and c["unpriced_calls"] == 0
    assert c["baseline_estimate_usd"] >= c["simulated_cost_usd"]
    assert {m["model_id"] for m in c["models"]} == {"mock:mock-small", "mock:mock-medium"}
    assert any("counterfactual" in n for n in c["notes"])


def test_settings_validation(client):
    ok = client.put("/api/settings", json={"similarity_threshold": 0.88, "routing_strategy": "cost_saver"}).json()
    assert ok["runtime"]["similarity_threshold"] == 0.88 and ok["runtime"]["routing_strategy"] == "cost_saver"
    assert client.put("/api/settings", json={"similarity_threshold": 3}).status_code == 422
    assert client.put("/api/settings", json={"routing_strategy": "yolo"}).status_code == 422
    assert client.put("/api/settings", json={}).status_code == 422


def test_monitoring_events_and_polling(client):
    upload(client)
    first = client.get("/api/monitoring/events").json()
    last = first[-1]["id"]
    ask(client, "How many days to request a refund?")
    new = client.get(f"/api/monitoring/events?after_id={last}").json()
    types = [e["type"] for e in new]
    assert types[:2] == ["query_received", "embedding"]
    assert {"cache_miss", "retrieval", "routing", "llm_call", "query_completed"} <= set(types)
    s = client.get("/api/monitoring/stats").json()
    assert s["total_processed"] == 1 and len(s["per_minute"]) == 30


def test_rate_limit(client, monkeypatch):
    from app import main
    from app.core.security import RateLimiter
    monkeypatch.setattr(main, "_limiter", RateLimiter(3))
    codes = [client.put("/api/settings", json={"cache_ttl_hours": 10}).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[3] == 429
