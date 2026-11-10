from app.models import LLMCall, RequestLog


def test_overview_empty_on_fresh_install(client):
    body = client.get("/api/metrics/overview").json()
    assert body["has_data"] is False
    assert body["total_queries"] == 0
    assert body["cache_hit_rate"] is None
    assert body["avg_latency_ms"] is None
    assert body["recent_activity"] == []


def test_overview_computes_from_real_rows(client, db_session):
    miss = RequestLog(query_text="q1", cache_status="miss", total_latency_ms=1000)
    miss.llm_calls.append(LLMCall(provider="mock", model="m", estimated_cost_usd=0.002))
    hit = RequestLog(query_text="q1 again", cache_status="semantic_hit", total_latency_ms=20)
    db_session.add_all([miss, hit])
    db_session.commit()

    body = client.get("/api/metrics/overview").json()
    assert body["has_data"] is True
    assert body["total_queries"] == 2
    assert body["cache_hit_rate"] == 0.5
    assert body["avg_latency_ms"] == 510.0
    assert body["llm_calls"] == 1
    assert body["llm_calls_avoided"] == 1
    assert abs(body["estimated_cost_usd"] - 0.002) < 1e-9
