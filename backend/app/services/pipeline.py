"""The NEXUS AI request pipeline.

    query -> validate -> embed -> semantic cache lookup
         hit : return validated cached answer (0 LLM tokens)
         miss: retrieve chunks -> analyse query -> route model -> LLM (with fallback)
               -> store in cache -> record tokens / cost / latency / events

`run()` is a generator of stage events (used for streaming to the browser and
for Live Monitoring); `execute()` drains it and returns the final result.

Modes (used by the Benchmarking Lab):
    baseline  - no cache, no routing (always the most capable available model)
    cache     - semantic cache on, routing off
    optimized - semantic cache on, routing on   (normal app behaviour)
"""
from __future__ import annotations

import time
import uuid
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.analytics.events import emit
from app.cache.semantic_cache import SemanticCache, scope_key
from app.core.config import get_settings
from app.core.errors import AppError
from app.embeddings import Embedder
from app.llm.base import LLMError, LLMRequest, LLMUsage
from app.llm.registry import ModelInfo, ModelRegistry, compute_cost
from app.models import CostRecord, LatencyRecord, LLMCall, RequestLog
from app.rag.prompt import NO_CONTEXT_ANSWER, SYSTEM_PROMPT, build_user_message
from app.rag.service import DocumentService, RetrievedChunk
from app.rag.vector_store import VectorStore
from app.router.model_router import NoModelAvailable, _sorted, route
from app.router.query_intelligence import analyze
from app.services.runtime_settings import get_runtime

MODES = ("baseline", "cache", "optimized")
MAX_ATTEMPTS = 3
CALCULATOR_PROMPT = "You are a precise calculator. Answer the arithmetic question directly and show the result."


@dataclass
class QueryInput:
    tenant: str
    query: str
    document_ids: list[int] | None = None
    model_id: str | None = None            # manual model selection
    mode: str = "optimized"
    source: str = "playground"
    conversation_id: str | None = None
    benchmark_run_id: int | None = None
    threshold: float | None = None          # override (threshold experiments / benchmarks)
    stream_delay_s: float = 0.0             # tiny pause when replaying cached text, purely cosmetic


@dataclass
class _Timer:
    stages: dict[str, float] = field(default_factory=dict)

    def run(self, name: str, fn, *a, **kw):
        t0 = time.perf_counter()
        try:
            return fn(*a, **kw)
        finally:
            self.stages[name] = round((time.perf_counter() - t0) * 1000, 2)


class QueryPipeline:
    def __init__(self, db: Session, store: VectorStore, embedder: Embedder, registry: ModelRegistry):
        self.db, self.store, self.embedder, self.registry = db, store, embedder, registry
        self.docs = DocumentService(db, store, embedder)
        self.cache = SemanticCache(db, store)
        self.settings = get_settings()

    # ------------------------------------------------------------ public
    def execute(self, inp: QueryInput) -> dict[str, Any]:
        result = None
        for ev in self.run(inp):
            if ev["type"] == "done":
                result = ev["result"]
        assert result is not None
        return result

    def run(self, inp: QueryInput) -> Generator[dict, None, None]:
        q = " ".join((inp.query or "").split())
        if not q:
            raise AppError("The question is empty.", 422, "empty_query")
        if len(q) > self.settings.max_query_chars:
            raise AppError(f"The question is longer than {self.settings.max_query_chars} characters.", 422, "query_too_long")
        if inp.mode not in MODES:
            raise AppError(f"Unknown mode '{inp.mode}'.", 422, "invalid_mode")

        rt = get_runtime(self.db)
        threshold = inp.threshold if inp.threshold is not None else float(rt["similarity_threshold"])
        use_cache = inp.mode != "baseline" and bool(rt["cache_enabled"])
        mock_mode = self.settings.mock_mode
        t_start = time.perf_counter()
        timer = _Timer()

        doc_ids = self.docs.indexed_ids(inp.tenant, inp.document_ids)
        scope = scope_key(inp.document_ids)
        req = RequestLog(tenant_id=inp.tenant, query_text=q, source=inp.source, mode=inp.mode,
                         conversation_id=inp.conversation_id or uuid.uuid4().hex[:16],
                         benchmark_run_id=inp.benchmark_run_id, scope_key=scope, document_ids=doc_ids,
                         is_mock=mock_mode, cache_status="miss")
        self.db.add(req)
        self.db.commit()
        rid = req.id
        yield {"type": "started", "request_id": rid, "conversation_id": req.conversation_id, "mock_mode": mock_mode}
        emit(self.db, "query_received", f"Query #{rid} received ({len(q)} chars, {len(doc_ids)} document(s) in scope)",
             tenant=inp.tenant, request_id=rid, data={"mode": inp.mode, "source": inp.source})

        try:
            # ---------------- 1. embedding
            vector = timer.run("embedding", lambda: self.embedder.embed([q])[0])
            emit(self.db, "embedding", f"Embedding generated in {timer.stages['embedding']:.0f} ms",
                 tenant=inp.tenant, request_id=rid, data={"ms": timer.stages["embedding"], "dim": int(vector.shape[0])})
            yield {"type": "stage", "stage": "embedding", "ms": timer.stages["embedding"]}

            # ---------------- 2. cache
            lookup = None
            if use_cache:
                lookup = timer.run("cache_lookup", self.cache.lookup, q, vector, inp.tenant, scope, threshold, mock_mode)
                req.similarity = lookup.similarity
                req.cache_reason = lookup.reason
                cand = [c.__dict__ for c in lookup.candidates]
                emit(self.db, "cache_hit" if lookup.hit else "cache_miss",
                     f"Cache {lookup.status.replace('_', ' ')}"
                     + (f" (similarity {lookup.similarity:.3f})" if lookup.similarity is not None else ""),
                     tenant=inp.tenant, request_id=rid,
                     data={"status": lookup.status, "similarity": lookup.similarity, "threshold": threshold,
                           "candidates": len(cand)})
                yield {"type": "cache", "status": lookup.status, "similarity": lookup.similarity,
                       "threshold": threshold, "reason": lookup.reason, "candidates": cand}
                if lookup.hit:
                    yield from self._serve_hit(req, lookup, timer, t_start, inp)
                    return
            else:
                req.cache_status = "bypass"
                req.cache_reason = "Cache disabled for this request (baseline mode or turned off in Settings)."
                yield {"type": "cache", "status": "bypass", "similarity": None, "threshold": threshold,
                       "reason": req.cache_reason, "candidates": []}

            # ---------------- 3. analysis + retrieval
            analysis = analyze(q, has_documents=bool(doc_ids))
            req.category, req.complexity, req.complexity_score = (analysis.category, analysis.complexity_level,
                                                                  analysis.complexity_score)
            req.analysis = analysis.to_dict()
            yield {"type": "analysis", "analysis": analysis.to_dict()}

            chunks: list[RetrievedChunk] = []
            if analysis.retrieval_required:
                chunks = timer.run("retrieval", self.docs.retrieve, inp.tenant, vector, doc_ids,
                                   int(rt["retrieval_top_k"]), float(rt["min_retrieval_score"]))
                req.retrieval_count = len(chunks)
                req.top_retrieval_score = round(chunks[0].score, 4) if chunks else None
                emit(self.db, "retrieval", f"Retrieved {len(chunks)} chunk(s)"
                     + (f", top score {chunks[0].score:.3f}" if chunks else ""), tenant=inp.tenant, request_id=rid,
                     data={"count": len(chunks), "top_score": req.top_retrieval_score,
                           "flagged": sum(c.flagged for c in chunks)})
            citations = [c.citation(i) for i, c in enumerate(chunks, start=1)]
            yield {"type": "retrieval", "count": len(chunks), "citations": citations,
                   "ms": timer.stages.get("retrieval")}

            if analysis.retrieval_required and not chunks:
                # Nothing relevant -> answer honestly without spending an LLM call.
                req.answer, req.citations, req.cache_status = NO_CONTEXT_ANSWER, [], "miss"
                req.usage_source, req.cost_status, req.cost_usd = "none", "none", 0.0
                yield {"type": "token", "text": NO_CONTEXT_ANSWER}
                yield self._finish(req, timer, t_start, None, [], llm_called=False)
                return

            # ---------------- 4. routing
            available = self.registry.available(self.db)
            try:
                decision = route(analysis, available, str(rt["routing_strategy"]), inp.model_id,
                                 baseline=inp.mode in ("baseline", "cache") and not inp.model_id)
            except NoModelAvailable as e:
                raise AppError(str(e), 503, "no_model_available") from e
            req.routed_by, req.routing_reason = decision.routed_by, decision.reason
            emit(self.db, "routing", f"Routed to {decision.model.display_name} ({decision.routed_by})",
                 tenant=inp.tenant, request_id=rid, data=decision.to_dict())
            yield {"type": "routing", "routing": decision.to_dict()}

            # ---------------- 5. LLM call with fallback
            system = SYSTEM_PROMPT if chunks else CALCULATOR_PROMPT
            user = build_user_message(q, chunks) if chunks else q
            mock_ctx = [{"index": i, "text": c.text} for i, c in enumerate(chunks, start=1)]
            attempts: list[dict] = []
            text_parts: list[str] = []
            usage: LLMUsage | None = None
            used: ModelInfo | None = None
            t_llm = time.perf_counter()
            for model in [decision.model, *decision.fallbacks][:MAX_ATTEMPTS]:
                cfg_effort = model.effort
                lreq = LLMRequest(model=model.model_name, system=system, user=user,
                                  max_output_tokens=self.settings.llm_max_output_tokens,
                                  timeout_s=self.settings.llm_timeout_seconds, effort=cfg_effort, mock_context=mock_ctx)
                t0 = time.perf_counter()
                try:
                    gen = self.registry.provider(model.provider).stream(lreq)
                    while True:
                        piece = next(gen)
                        text_parts.append(piece)
                        yield {"type": "token", "text": piece}
                except StopIteration as stop:
                    usage, used = stop.value, model
                    attempts.append({"model_id": model.id, "ok": True, "ms": round((time.perf_counter() - t0) * 1000, 1)})
                    break
                except LLMError as e:
                    ms = round((time.perf_counter() - t0) * 1000, 1)
                    attempts.append({"model_id": model.id, "ok": False, "error": e.kind, "ms": ms})
                    self.db.add(LLMCall(request_id=rid, tenant_id=inp.tenant, provider=model.provider,
                                        model=model.model_name, success=False, error_type=e.kind, latency_ms=ms,
                                        purpose="answer", is_mock=model.is_mock, usage_source="none"))
                    emit(self.db, "llm_error", f"{model.display_name} failed: {e.kind}", tenant=inp.tenant,
                         request_id=rid, level="warning", data={"model_id": model.id, "error": e.kind})
                    if text_parts:          # failed mid-stream: cannot transparently retry
                        raise AppError(f"The model stopped mid-answer ({e.kind}).", 502, "llm_failed") from e
                    yield {"type": "fallback", "failed_model": model.id, "error": e.kind}
                    continue
            if usage is None or used is None:
                raise AppError("All candidate models failed: " + ", ".join(f"{a['model_id']} ({a.get('error')})"
                                                                         for a in attempts), 502, "llm_failed")
            timer.stages["llm"] = round((time.perf_counter() - t_llm) * 1000, 2)
            req.fallback_used = used.id != decision.model.id
            if req.fallback_used:
                emit(self.db, "fallback", f"Fell back to {used.display_name}", tenant=inp.tenant, request_id=rid,
                     level="warning", data={"from": decision.model.id, "to": used.id})

            answer = "".join(text_parts).strip()
            cost, cost_status = compute_cost(self.db, used.id, usage.input_tokens, usage.output_tokens)
            req.answer, req.citations = answer, citations
            req.selected_model, req.provider = used.id, used.provider
            req.input_tokens, req.output_tokens, req.usage_source = usage.input_tokens, usage.output_tokens, usage.source
            req.cost_usd, req.cost_status = (cost or 0.0), cost_status
            basis = "simulated" if cost_status == "simulated" else (
                "provider_tokens" if usage.source == "provider" else "estimated_tokens")
            self.db.add(LLMCall(request_id=rid, tenant_id=inp.tenant, provider=used.provider, model=used.model_name,
                                input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                                usage_source=usage.source, estimated_cost_usd=cost or 0.0, cost_status=cost_status,
                                latency_ms=timer.stages["llm"], served_model=usage.served_model, purpose="answer",
                                is_mock=used.is_mock, success=True))
            if cost is not None:
                self.db.add(CostRecord(tenant_id=inp.tenant, request_id=rid, kind="actual", model=used.id,
                                       amount_usd=cost, basis=basis))
            # counterfactual routing saving: same tokens on the baseline (largest) model
            if decision.routed_by == "auto" and cost is not None:
                baseline_model = _sorted(available, "large")[0]
                if baseline_model.id != used.id:
                    b_cost, _ = compute_cost(self.db, baseline_model.id, usage.input_tokens, usage.output_tokens)
                    if b_cost is not None and b_cost > cost:
                        req.saved_cost_routing = round(b_cost - cost, 8)
                        self.db.add(CostRecord(tenant_id=inp.tenant, request_id=rid, kind="routing_saving",
                                               model=baseline_model.id, amount_usd=req.saved_cost_routing, basis=basis))
            emit(self.db, "llm_call", f"{used.display_name}: {usage.input_tokens} in / {usage.output_tokens} out tokens "
                 f"({usage.source}), {timer.stages['llm']:.0f} ms", tenant=inp.tenant, request_id=rid,
                 data={"model_id": used.id, "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
                       "usage_source": usage.source, "cost_usd": cost, "cost_status": cost_status,
                       "ms": timer.stages["llm"]})

            # ---------------- 6. store in cache
            if use_cache and answer:
                source_versions = {str(c.document_id): c.document_version for c in chunks}
                entry = timer.run("cache_store", self.cache.store_answer, query=q, vector=vector, tenant=inp.tenant,
                                  scope=scope, answer=answer, citations=citations, source_versions=source_versions,
                                  model=used.id, provider=used.provider, is_mock=used.is_mock,
                                  input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                                  cost_usd=cost or 0.0, latency_ms=timer.stages["llm"],
                                  ttl_hours=int(rt["cache_ttl_hours"]), request_id=rid)
                req.cache_entry_id = entry.id

            yield self._finish(req, timer, t_start, used, attempts, llm_called=True, decision=decision.to_dict())
        except AppError as e:
            self._fail(req, e.message, timer, t_start)
            raise
        except Exception as e:
            self._fail(req, f"{type(e).__name__}", timer, t_start)
            raise

    # ------------------------------------------------------------ helpers
    def _serve_hit(self, req: RequestLog, lookup, timer: _Timer, t_start: float, inp: QueryInput):
        e = lookup.entry
        self.cache.record_hit(e, lookup.similarity or 1.0)
        req.cache_status, req.cache_entry_id = lookup.status, e.id
        req.answer, req.citations = e.response_text, e.citations or []
        req.selected_model, req.provider = e.model, e.provider
        req.usage_source, req.cost_status, req.cost_usd = "none", "none", 0.0
        req.input_tokens = req.output_tokens = 0
        req.saved_cost_cache = float(e.original_cost_usd or 0.0)
        if req.saved_cost_cache:
            self.db.add(CostRecord(tenant_id=req.tenant_id, request_id=req.id, kind="cache_saving", model=e.model,
                                   amount_usd=req.saved_cost_cache, basis="simulated" if e.is_mock else "estimated_tokens"))
        text = e.response_text
        for i in range(0, len(text), 48):
            if inp.stream_delay_s:
                time.sleep(inp.stream_delay_s)
            yield {"type": "token", "text": text[i:i + 48]}
        yield {"type": "retrieval", "count": len(req.citations), "citations": req.citations, "ms": None}
        yield self._finish(req, timer, t_start, None, [], llm_called=False, cache_entry=e)

    def _fail(self, req: RequestLog, message: str, timer: _Timer, t_start: float) -> None:
        self.db.rollback()
        req = self.db.get(RequestLog, req.id) or req
        req.cache_status = "error" if req.cache_status not in ("exact_hit", "semantic_hit") else req.cache_status
        req.error = message[:500]
        req.total_latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
        req.stage_timings = timer.stages
        self.db.commit()
        emit(self.db, "error", f"Query #{req.id} failed: {message[:200]}", tenant=req.tenant_id, request_id=req.id,
             level="error")

    def _finish(self, req: RequestLog, timer: _Timer, t_start: float, used: ModelInfo | None, attempts: list,
                llm_called: bool, decision: dict | None = None, cache_entry=None) -> dict:
        total = round((time.perf_counter() - t_start) * 1000, 2)
        timer.stages["total"] = total
        req.total_latency_ms, req.stage_timings = total, timer.stages
        for stage, ms in timer.stages.items():
            self.db.add(LatencyRecord(request_id=req.id, stage=stage, duration_ms=ms))
        self.db.commit()
        emit(self.db, "query_completed", f"Query #{req.id} completed in {total:.0f} ms ({req.cache_status})",
             tenant=req.tenant_id, request_id=req.id,
             data={"cache_status": req.cache_status, "ms": total, "model": req.selected_model, "llm_called": llm_called})
        return {"type": "done", "result": serialize_request(req, attempts=attempts, llm_called=llm_called,
                                                            routing=decision, cache_entry=cache_entry)}


def serialize_request(req: RequestLog, attempts: list | None = None, llm_called: bool | None = None,
                      routing: dict | None = None, cache_entry=None) -> dict:
    return {
        "request_id": req.id,
        "conversation_id": req.conversation_id,
        "query": req.query_text,
        "answer": req.answer,
        "is_mock": bool(req.is_mock),
        "mode": req.mode,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "cache": {"status": req.cache_status, "similarity": req.similarity, "reason": req.cache_reason,
                  "entry_id": req.cache_entry_id,
                  "matched_query": cache_entry.query_text if cache_entry is not None else None,
                  "entry_created_at": cache_entry.created_at.isoformat() if cache_entry is not None else None},
        "analysis": req.analysis,
        "routing": routing or ({"routed_by": req.routed_by, "reason": req.routing_reason, "model_id": req.selected_model}
                               if req.routed_by else None),
        "model": {"id": req.selected_model, "provider": req.provider},
        "citations": req.citations or [],
        "usage": {"input_tokens": req.input_tokens or 0, "output_tokens": req.output_tokens or 0,
                  "source": req.usage_source},
        "cost": {"usd": req.cost_usd or 0.0, "status": req.cost_status,
                 "saved_by_cache_usd": req.saved_cost_cache or 0.0, "saved_by_routing_usd": req.saved_cost_routing or 0.0,
                 "note": "Costs are estimates: tokens x list price. Savings are counterfactual estimates."},
        "latency_ms": req.total_latency_ms,
        "stage_timings": req.stage_timings or {},
        "fallback_used": bool(req.fallback_used),
        "attempts": attempts or [],
        "llm_called": llm_called,
        "retrieval": {"count": req.retrieval_count or 0, "top_score": req.top_retrieval_score},
        "error": req.error,
    }
