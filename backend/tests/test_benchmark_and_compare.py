"""Benchmarking Lab and Model Comparison Lab."""
from app.evaluation import benchmark
from app.evaluation.quality import correctness, faithfulness, retrieval_hit
from app.models import BenchmarkRun
from tests.conftest import upload


def test_quality_metrics(env):
    assert correctness("The window is 30 days [1].", [["30", "thirty"], ["days"]]) == 1.0
    assert correctness("No idea.", [["30"]]) == 0.0
    assert correctness("anything", []) is None
    assert retrieval_hit([{"filename": "a.txt"}], "a.txt") == 1.0
    assert retrieval_hit([{"filename": "b.txt"}], "a.txt") == 0.0
    ctx = ["Customers can request a full refund within 30 days of purchase."]
    assert faithfulness("Customers can request a full refund within 30 days of purchase.", ctx, env.embedder) == 1.0


def test_benchmark_run_end_to_end(client, env):
    upload(client)    # user data that must stay untouched
    r = client.post("/api/benchmarks/runs", json={"name": "t", "configs": ["baseline", "cache", "optimized"]})
    assert r.status_code == 202
    run_id = r.json()["id"]
    # the API started it in a thread; wait for it to finish
    import time
    for _ in range(300):
        d = client.get(f"/api/benchmarks/runs/{run_id}").json()
        if d["status"] in ("completed", "failed"):
            break
        time.sleep(0.1)
    assert d["status"] == "completed", d.get("error")
    assert d["is_simulated"] is True and "TEST MODE" in d["summary"]["note"]
    cfg = d["summary"]["configs"]
    assert set(cfg) == {"baseline", "cache", "optimized"}
    n = cfg["baseline"]["questions"]
    assert len(d["results"]) == 3 * n
    assert cfg["baseline"]["cache_hit_rate"] == 0 and cfg["baseline"]["llm_calls_avoided"] == 0
    assert cfg["cache"]["llm_calls_avoided"] >= 1          # the dataset repeats one question exactly
    for k in ("avg_latency_ms", "median_latency_ms", "p95_latency_ms", "input_tokens", "output_tokens", "cost_usd",
              "retrieval_relevance", "answer_correctness", "answer_faithfulness"):
        assert k in cfg["optimized"]
    assert "cost_reduction_vs_baseline" in cfg["optimized"]
    # isolation: benchmark tenant cleaned up, user library untouched
    assert client.get("/api/documents", headers={"X-Tenant-ID": f"bench-{run_id}"}).json() == []
    assert len(client.get("/api/documents").json()) == 1
    md = client.get(f"/api/benchmarks/runs/{run_id}/report?format=md")
    assert md.status_code == 200 and "TEST MODE" in md.text
    csv = client.get(f"/api/benchmarks/runs/{run_id}/report?format=csv").text.strip().splitlines()
    assert len(csv) == 1 + 3 * n
    assert client.delete(f"/api/benchmarks/runs/{run_id}").status_code == 200


def test_benchmark_requires_cost_confirmation_with_real_providers(client, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(type(get_settings()), "mock_mode", property(lambda self: False))
    r = client.post("/api/benchmarks/runs", json={"name": "paid"})
    assert r.status_code == 402 and r.json()["error"]["code"] == "confirm_cost"
    assert r.json()["error"]["max_llm_calls"] == 66


def test_benchmark_failure_is_recorded(env):
    run = BenchmarkRun(name="bad", dataset="does-not-exist", configs=["baseline"])
    env.db.add(run)
    env.db.commit()
    benchmark.start_run(run.id, background=False)
    env.db.expire_all()
    assert env.db.get(BenchmarkRun, run.id).status == "failed"


def test_compare_uses_identical_context(client):
    upload(client)
    r = client.post("/api/compare", json={"query": "What does the Pro plan include?",
                                          "model_ids": ["mock:mock-small", "mock:mock-large"],
                                          "reference_answer": "The Pro plan costs 49 dollars and includes priority support."})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["is_mock"] is True and len(d["results"]) == 2 and d["context"]
    a, b = d["results"]
    assert a["input_tokens"] == b["input_tokens"]           # same prompt for every model
    assert a["cost_status"] == b["cost_status"] == "simulated" and b["cost_usd"] > a["cost_usd"]
    assert a["reference_similarity"] is not None and a["faithfulness"] is not None
    rep = client.get(f"/api/compare/{d['id']}/report")
    assert rep.status_code == 200 and "identical retrieved context" in rep.text
    assert client.get("/api/compare").json()[0]["id"] == d["id"]


def test_compare_validation(client):
    upload(client)
    r = client.post("/api/compare", json={"query": "Pro plan?", "model_ids": ["anthropic:claude-opus-5-5"]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "model_unavailable"
