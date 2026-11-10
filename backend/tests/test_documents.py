"""Document upload / validation / versioning / deletion / tenant isolation."""
from tests.conftest import POLICY, ask, upload
from tests.fixtures.make_pdf import make_pdf


def test_upload_txt_and_pdf_and_list(client):
    r = upload(client)
    assert r["status"] == "created" and r["document"]["chunk_count"] >= 1
    pdf = make_pdf(["Annual leave is 25 days per year for full-time staff.", "Remote work is allowed 3 days a week."])
    r2 = client.post("/api/documents", files=[("files", ("handbook.pdf", pdf, "application/pdf"))]).json()["results"][0]
    assert r2["status"] == "created" and r2["document"]["page_count"] == 2
    docs = client.get("/api/documents").json()
    assert {d["filename"] for d in docs} == {"policy.txt", "handbook.pdf"}
    chunks = client.get(f"/api/documents/{r2['document']['id']}/chunks").json()
    assert {c["page"] for c in chunks["chunks"]} == {1, 2}


def test_duplicate_upload_detected(client):
    upload(client)
    again = upload(client, name="copy.txt")
    assert again["status"] == "duplicate"
    assert len(client.get("/api/documents").json()) == 1


def test_rejects_bad_files(client, monkeypatch):
    files = [("files", ("virus.exe", b"MZ....", "application/octet-stream")),
             ("files", ("fake.pdf", b"hello", "application/pdf")),
             ("files", ("empty.txt", b"", "text/plain"))]
    results = client.post("/api/documents", files=files).json()["results"]
    assert [r["status"] for r in results] == ["rejected"] * 3
    assert results[0]["code"] == "unsupported_type" and results[1]["code"] == "invalid_pdf"

    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    big = client.post("/api/documents", files=[("files", ("big.txt", b"a" * 1_100_000, "text/plain"))])
    assert big.json()["results"][0]["code"] == "file_too_large"


def test_filename_is_sanitised(client):
    r = upload(client, name="../../etc/passwd.txt", data=b"Some harmless text about refunds and invoices.")
    assert r["document"]["filename"] == "passwd.txt"


def test_update_creates_new_version_and_invalidates_cache(client):
    doc = upload(client)["document"]
    first = ask(client, "How many days to request a refund?")
    assert first["cache"]["status"] == "miss" and "30 days" in first["answer"]
    assert ask(client, "How many days to request a refund?")["cache"]["status"] == "exact_hit"

    new = POLICY.replace(b"30 days", b"14 days")
    r = client.put(f"/api/documents/{doc['id']}", files={"file": ("policy.txt", new, "text/plain")}).json()
    assert r["document"]["version"] == 2 and r["cache_entries_invalidated"] == 1
    after = ask(client, "How many days to request a refund?")
    assert after["cache"]["status"] == "miss"            # old answer is never served again
    assert "14 days" in after["answer"] and "30 days" not in after["answer"]


def test_update_with_identical_content_is_rejected(client):
    doc = upload(client)["document"]
    r = client.put(f"/api/documents/{doc['id']}", files={"file": ("policy.txt", POLICY, "text/plain")})
    assert r.status_code == 409


def test_delete_removes_document_vectors_and_cache(client, env):
    doc = upload(client)["document"]
    ask(client, "How many days to request a refund?")
    r = client.delete(f"/api/documents/{doc['id']}").json()
    assert r["cache_entries_invalidated"] == 1
    assert client.get("/api/documents").json() == []
    assert env.store.docs.count() == 0
    res = ask(client, "How many days to request a refund?")
    assert res["llm_called"] is False and "do not contain enough information" in res["answer"]


def test_tenant_isolation(client):
    doc = upload(client, tenant="alice")["document"]
    ask(client, "How many days to request a refund?", tenant="alice")
    assert client.get("/api/documents", headers={"X-Tenant-ID": "bob"}).json() == []
    assert client.get(f"/api/documents/{doc['id']}", headers={"X-Tenant-ID": "bob"}).status_code == 404
    assert client.delete(f"/api/documents/{doc['id']}", headers={"X-Tenant-ID": "bob"}).status_code == 404
    bob = ask(client, "How many days to request a refund?", tenant="bob")
    assert bob["cache"]["status"] == "miss"     # alice's cached answer is never visible to bob
    assert bob["llm_called"] is False and bob["citations"] == []
    r = client.post("/api/query", json={"query": "refund?", "document_ids": [doc["id"]]}, headers={"X-Tenant-ID": "bob"})
    assert r.status_code == 404
    assert client.get("/api/documents", headers={"X-Tenant-ID": "../x"}).status_code == 400
