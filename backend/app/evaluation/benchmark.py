"""Benchmarking Lab runner.

Configurations (identical questions, documents and settings):
  baseline   A. plain RAG: no cache, no routing (most capable available model)
  cache      B. semantic cache on, routing off
  optimized  C. semantic cache + intelligent routing

Each run gets its own isolated tenant ("bench-<run id>"), so it never touches
your library or cache, and every configuration starts with an EMPTY cache.
All numbers are measured from the actual execution. When test mode is on,
the run is marked `is_simulated` and every chart says so.
"""
from __future__ import annotations

import csv
import io
import threading
import traceback
from datetime import datetime, timezone

import numpy as np
from sqlalchemy.orm import Session

from app.analytics.events import emit
from app.cache.semantic_cache import SemanticCache
from app.core.config import get_settings
from app.core.logging import get_logger
from app.database import SessionLocal
from app.embeddings import get_embedder
from app.evaluation import quality
from app.evaluation.datasets import load_dataset
from app.llm.registry import get_registry
from app.models import BenchmarkResult, BenchmarkRun, DocumentChunk
from app.rag.service import DocumentService
from app.rag.vector_store import get_vector_store
from app.services.pipeline import QueryInput, QueryPipeline

log = get_logger("benchmark")
CONFIG_LABELS = {"baseline": "A. Baseline RAG", "cache": "B. RAG + semantic cache",
                 "optimized": "C. RAG + cache + routing"}
_running: set[int] = set()


def _summary(results: list[BenchmarkResult]) -> dict:
    lat = [r.latency_ms for r in results]
    n = len(results)
    hits = sum(r.cache_status in ("exact_hit", "semantic_hit") for r in results)

    def mean(xs):
        xs = [x for x in xs if x is not None]
        return round(float(np.mean(xs)), 4) if xs else None

    return {
        "questions": n,
        "avg_latency_ms": round(float(np.mean(lat)), 1) if lat else None,
        "median_latency_ms": round(float(np.median(lat)), 1) if lat else None,
        "p95_latency_ms": round(float(np.percentile(lat, 95)), 1) if lat else None,
        "cache_hit_rate": round(hits / n, 4) if n else None,
        "cache_miss_rate": round(1 - hits / n, 4) if n else None,
        "llm_calls": sum(r.llm_called for r in results),
        "llm_calls_avoided": hits,
        "input_tokens": sum(r.input_tokens for r in results),
        "output_tokens": sum(r.output_tokens for r in results),
        "cost_usd": round(sum(r.cost_usd for r in results), 6),
        "retrieval_relevance": mean([r.retrieval_hit for r in results]),
        "answer_correctness": mean([r.correctness for r in results]),
        "answer_faithfulness": mean([r.faithfulness for r in results]),
        "models_used": sorted({r.model for r in results if r.model and r.llm_called}),
    }


def _execute(run_id: int) -> None:
    db: Session = SessionLocal()
    run = db.get(BenchmarkRun, run_id)
    tenant = f"bench-{run_id}"
    store, embedder, registry = get_vector_store(), get_embedder(), get_registry()
    docs = DocumentService(db, store, embedder)
    cache = SemanticCache(db, store)
    try:
        run.status, run.is_simulated = "running", get_settings().mock_mode
        db.commit()
        emit(db, "benchmark_started", f"Benchmark #{run_id} started ({', '.join(run.configs)})", tenant=run.tenant_id)
        ds = load_dataset(run.dataset)
        for d in ds["documents"]:
            docs.upload(tenant, d["filename"], d["text"].encode("utf-8"))
        pipeline = QueryPipeline(db, store, embedder, registry)
        threshold = (run.settings or {}).get("threshold")
        total = len(run.configs) * len(ds["questions"])
        done = 0
        summary: dict = {"configs": {}}
        for cfg in run.configs:
            cache.clear(tenant)                      # every configuration starts with an empty cache
            rows: list[BenchmarkResult] = []
            for q in ds["questions"]:
                res = pipeline.execute(QueryInput(tenant=tenant, query=q["question"], mode=cfg, source="benchmark",
                                                  benchmark_run_id=run_id, threshold=threshold))
                # the exact passages the answer was grounded on (for the faithfulness metric)
                cited = {(c["document_id"], c["chunk_index"]) for c in res["citations"]}
                ctx = [c.text for c in db.query(DocumentChunk).filter(DocumentChunk.tenant_id == tenant)
                       if (c.document_id, c.chunk_index) in cited]
                answer = res["answer"] or ""
                r = BenchmarkResult(
                    run_id=run_id, config=cfg, question_id=q["id"], question=q["question"],
                    cache_status=res["cache"]["status"], model=res["model"]["id"],
                    complexity=(res["analysis"] or {}).get("complexity_level"), latency_ms=res["latency_ms"] or 0.0,
                    input_tokens=res["usage"]["input_tokens"], output_tokens=res["usage"]["output_tokens"],
                    cost_usd=res["cost"]["usd"] or 0.0, llm_called=bool(res["llm_called"]),
                    retrieval_hit=quality.retrieval_hit(res["citations"], q.get("gold_document")),
                    correctness=quality.correctness(answer, q.get("expected_keywords") or []),
                    faithfulness=quality.faithfulness(answer, ctx, embedder), answer=answer[:4000])
                db.add(r)
                rows.append(r)
                done += 1
                run.progress = round(done / total, 4)
                db.commit()
            summary["configs"][cfg] = {"label": CONFIG_LABELS[cfg], **_summary(rows)}
        base = summary["configs"].get("baseline")
        if base:
            for cfg, s in summary["configs"].items():
                if cfg == "baseline":
                    continue
                s["cost_reduction_vs_baseline"] = (round(1 - s["cost_usd"] / base["cost_usd"], 4)
                                                   if base["cost_usd"] else None)
                s["latency_reduction_vs_baseline"] = (round(1 - s["avg_latency_ms"] / base["avg_latency_ms"], 4)
                                                      if base["avg_latency_ms"] else None)
        summary["is_simulated"] = run.is_simulated
        summary["note"] = ("TEST MODE: answers came from the mock provider; costs are SIMULATED with real list prices "
                           "of the models the mocks stand in for. Latency reflects local processing, not real LLM latency."
                           if run.is_simulated else
                           "Measured with real LLM calls. Costs are estimates (tokens x list price).")
        _cleanup(docs, cache, tenant, run_id)           # clean up BEFORE reporting completion
        run.summary, run.status, run.progress = summary, "completed", 1.0
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        emit(db, "benchmark_completed", f"Benchmark #{run_id} completed", tenant=run.tenant_id)
    except Exception as exc:
        log.error("Benchmark %s failed: %s", run_id, traceback.format_exc(limit=3))
        db.rollback()
        _cleanup(docs, cache, tenant, run_id)
        run = db.get(BenchmarkRun, run_id)
        run.status, run.error = "failed", f"{type(exc).__name__}: {str(exc)[:300]}"
        db.commit()
        emit(db, "error", f"Benchmark #{run_id} failed: {type(exc).__name__}", tenant=run.tenant_id, level="error")
    finally:
        _running.discard(run_id)
        db.close()


def _cleanup(docs: DocumentService, cache: SemanticCache, tenant: str, run_id: int) -> None:
    """Remove the isolated tenant's documents, vectors and cache (results are kept)."""
    try:
        for d in docs.list(tenant):
            docs.delete(tenant, d.id, cache)
        cache.clear(tenant)
    except Exception:
        log.warning("Benchmark %s cleanup incomplete", run_id)


def start_run(run_id: int, background: bool = True) -> None:
    _running.add(run_id)
    if background:
        threading.Thread(target=_execute, args=(run_id,), daemon=True, name=f"benchmark-{run_id}").start()
    else:
        _execute(run_id)


def is_running() -> bool:
    return bool(_running)


def report(run: BenchmarkRun, fmt: str) -> tuple[str, str]:
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["config", "question_id", "question", "cache_status", "model", "complexity", "latency_ms",
                    "input_tokens", "output_tokens", "cost_usd", "llm_called", "retrieval_hit", "correctness",
                    "faithfulness"])
        for r in run.results:
            w.writerow([r.config, r.question_id, r.question, r.cache_status, r.model, r.complexity, r.latency_ms,
                        r.input_tokens, r.output_tokens, r.cost_usd, r.llm_called, r.retrieval_hit, r.correctness,
                        r.faithfulness])
        return buf.getvalue(), "text/csv"
    s = run.summary or {}
    lines = [f"# NEXUS AI benchmark report - run #{run.id}", "",
             f"* Name: {run.name}", f"* Dataset: {run.dataset}", f"* Created: {run.created_at.isoformat()}",
             f"* Status: {run.status}",
             f"* Mode: {'TEST MODE (mock LLM, simulated costs)' if run.is_simulated else 'real LLM calls'}",
             f"* Threshold: {(run.settings or {}).get('threshold') or 'runtime setting'}", "",
             f"> {s.get('note', '')}", "", "## Results", "",
             "| Metric | " + " | ".join(c.get("label", k) for k, c in s.get("configs", {}).items()) + " |",
             "|---|" + "---|" * len(s.get("configs", {}))]
    metrics = [("avg_latency_ms", "Average latency (ms)"), ("median_latency_ms", "Median latency (ms)"),
               ("p95_latency_ms", "P95 latency (ms)"), ("cache_hit_rate", "Cache hit rate"),
               ("llm_calls", "LLM calls"), ("llm_calls_avoided", "LLM calls avoided"),
               ("input_tokens", "Input tokens"), ("output_tokens", "Output tokens"), ("cost_usd", "Cost (USD, est.)"),
               ("cost_reduction_vs_baseline", "Cost reduction vs A"),
               ("latency_reduction_vs_baseline", "Latency reduction vs A"),
               ("retrieval_relevance", "Retrieval relevance"), ("answer_correctness", "Answer correctness (keywords)"),
               ("answer_faithfulness", "Answer faithfulness (heuristic)")]
    for key, label in metrics:
        lines.append(f"| {label} | " + " | ".join(str(c.get(key, "-")) for c in s.get("configs", {}).values()) + " |")
    lines += ["", "Quality metrics are automatic heuristics (keyword match, embedding similarity), not human ratings."]
    return "\n".join(lines) + "\n", "text/markdown"
