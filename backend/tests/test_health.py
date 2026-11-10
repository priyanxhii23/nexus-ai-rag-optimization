from app.models import Document, LLMCall, RequestLog


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["health"] == "/api/health"


def test_health_reports_ok_database(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["components"]["database"]["status"] == "ok"
    for table in ("documents", "request_logs", "llm_calls"):
        assert table in body["components"]["database"]["detail"]


def test_health_never_leaks_api_keys(client, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-secret-123")
    body = client.get("/api/health").text
    assert "sk-secret-123" not in body
    assert '"anthropic":true' in body.replace(" ", "")


def test_models_persist_and_link(db_session):
    doc = Document(filename="policy.pdf", content_hash="abc", size_bytes=10)
    req = RequestLog(query_text="What is the refund policy?")
    req.llm_calls.append(LLMCall(provider="mock", model="mock-small", input_tokens=50,
                                 output_tokens=20, usage_source="mock"))
    db_session.add_all([doc, req])
    db_session.commit()

    assert doc.tenant_id == "local" and doc.version == 1
    saved = db_session.get(RequestLog, req.id)
    assert saved.cache_status == "miss"
    assert saved.llm_calls[0].usage_source == "mock"
