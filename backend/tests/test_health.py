from app.models import Document, LLMCall, RequestLog


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["health"] == "/api/health"


def test_health_reports_components(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    for name in ("database", "vector_store", "embeddings", "llm"):
        assert body["components"][name]["status"] == "ok", name
    assert body["mock_mode"] is True
    assert "TEST MODE" in body["components"]["llm"]["detail"]
    assert body["models_available"] == 3


def test_health_never_leaks_api_keys(client, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-secret-123")
    body = client.get("/api/health").text + client.get("/api/settings").text + client.get("/api/models").text
    assert "sk-secret-123" not in body
    assert '"anthropic":true' in client.get("/api/health").text.replace(" ", "")


def test_swagger_docs_available(client):
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/api/health", "/api/documents", "/api/query", "/api/query/stream", "/api/cache/entries",
              "/api/models", "/api/compare", "/api/benchmarks/runs", "/api/monitoring/events", "/api/settings"):
        assert p in paths, p


def test_models_persist_and_link(db_session):
    doc = Document(filename="policy.pdf", content_hash="abc", size_bytes=10)
    req = RequestLog(query_text="What is the refund policy?")
    req.llm_calls.append(LLMCall(provider="mock", model="mock-small", input_tokens=50, output_tokens=20,
                                 usage_source="mock"))
    db_session.add_all([doc, req])
    db_session.commit()
    assert doc.tenant_id == "local" and doc.version == 1
    saved = db_session.get(RequestLog, req.id)
    assert saved.cache_status == "miss"
    assert saved.llm_calls[0].usage_source == "mock"
    assert saved.created_at.tzinfo is not None   # timestamps come back timezone-aware (UTC)


def test_security_headers_and_request_id(client):
    r = client.get("/api/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers.get("X-Request-ID")


def test_cors_allows_localhost_and_127(client):
    for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        r = client.options("/api/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
        assert r.status_code == 200
        assert r.headers["access-control-allow-origin"] == origin
    r = client.options("/api/health", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers


def test_error_shape(client):
    r = client.get("/api/documents/999")
    assert r.status_code == 404
    err = r.json()["error"]
    assert err["code"] == "not_found" and err["request_id"]
    r = client.post("/api/query", json={"query": "   "})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
