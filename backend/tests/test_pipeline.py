"""End-to-end pipeline: routing, fallback, costs, streaming, no-context handling."""
import json

from app.llm.base import LLMError, LLMProvider, LLMUsage
from app.llm.mock import MOCK_BANNER, MockProvider
from app.models import CostRecord, LLMCall, RequestLog
from tests.conftest import ask, upload


def test_answer_is_grounded_cited_and_labelled_mock(client):
    upload(client)
    r = ask(client, "How many days to request a refund?")
    assert r["answer"].startswith(MOCK_BANNER)          # mock output is always labelled
    assert r["is_mock"] is True and r["llm_called"] is True
    assert r["citations"] and r["citations"][0]["filename"] == "policy.txt"
    assert r["model"]["id"] == "mock:mock-small"          # simple question -> small tier
    assert r["usage"]["source"] == "mock"
    assert r["cost"]["status"] == "simulated" and r["cost"]["usd"] > 0
    assert set(r["stage_timings"]) >= {"embedding", "cache_lookup", "retrieval", "llm", "total"}


def test_routing_saving_is_recorded_as_counterfactual(client, env):
    upload(client)
    r = ask(client, "How many days to request a refund?")
    assert r["cost"]["saved_by_routing_usd"] > 0
    kinds = {c.kind for c in env.db.query(CostRecord)}
    assert kinds == {"actual", "routing_saving"}


def test_no_documents_means_no_llm_call(client):
    r = ask(client, "What is the refund policy?")
    assert r["llm_called"] is False and r["cost"]["usd"] == 0
    assert "do not contain enough information" in r["answer"]


def test_manual_model_selection(client):
    upload(client)
    r = ask(client, "How many days to request a refund?", model_id="mock:mock-large")
    assert r["model"]["id"] == "mock:mock-large" and r["routing"]["routed_by"] == "manual"


def test_baseline_mode_skips_cache_and_routing(client):
    upload(client)
    ask(client, "How many days to request a refund?", mode="baseline")
    r = ask(client, "How many days to request a refund?", mode="baseline")
    assert r["cache"]["status"] == "bypass" and r["routing"]["routed_by"] == "baseline"
    assert r["model"]["id"] == "mock:mock-large"


class FailingProvider(LLMProvider):
    name = "mock"
    is_mock = True

    def __init__(self, fail_models):
        self.fail_models, self.inner = set(fail_models), MockProvider()

    def stream(self, req):
        if req.model in self.fail_models:
            raise LLMError("simulated outage", "server_error")
        return self.inner.stream(req)


def test_fallback_to_next_model_when_provider_fails(client, env, monkeypatch):
    upload(client)
    env.registry._providers["mock"] = FailingProvider({"mock-small"})
    r = ask(client, "How many days to request a refund?")
    assert r["fallback_used"] is True and r["model"]["id"] != "mock:mock-small"
    assert [a["ok"] for a in r["attempts"]] == [False, True]
    failed = env.db.query(LLMCall).filter(LLMCall.success.is_(False)).one()
    assert failed.error_type == "server_error"


def test_all_models_failing_returns_clear_error(client, env):
    upload(client)
    env.registry._providers["mock"] = FailingProvider({"mock-small", "mock-medium", "mock-large"})
    r = client.post("/api/query", json={"query": "How many days to request a refund?"})
    assert r.status_code == 502 and r.json()["error"]["code"] == "llm_failed"
    assert env.db.query(RequestLog).one().cache_status == "error"


def test_streaming_endpoint_event_order(client):
    upload(client)
    with client.stream("POST", "/api/query/stream", json={"query": "How many days to request a refund?"}) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    types = [e["type"] for e in events]
    assert types[0] == "started" and types[-1] == "done"
    for t in ("stage", "cache", "analysis", "retrieval", "routing", "token"):
        assert t in types
    assert types.index("cache") < types.index("routing") < types.index("token")
    streamed = "".join(e["text"] for e in events if e["type"] == "token")
    assert streamed.strip() == events[-1]["result"]["answer"]


def test_streaming_reports_errors_as_events(client):
    with client.stream("POST", "/api/query/stream", json={"query": "x", "document_ids": [999]}) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    assert events[-1]["type"] == "error" and events[-1]["code"] == "not_found"


def test_history_and_request_detail(client):
    upload(client)
    r = ask(client, "How many days to request a refund?", conversation_id="conv1")
    hist = client.get("/api/query/history?conversation_id=conv1").json()
    assert [h["request_id"] for h in hist] == [r["request_id"]]
    detail = client.get(f"/api/query/{r['request_id']}").json()
    assert detail["llm_calls"][0]["usage_source"] == "mock"


def test_query_length_limit(client, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "max_query_chars", 50)
    r = client.post("/api/query", json={"query": "x" * 60})
    assert r.status_code == 422 and r.json()["error"]["code"] == "query_too_long"


def test_usage_dataclass_labels():
    u = LLMUsage(1, 2, "provider")
    assert u.source == "provider"
