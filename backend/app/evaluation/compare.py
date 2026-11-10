"""Multi-Model Comparison Lab.

Fairness: retrieval runs ONCE and every model receives the identical system
prompt and user message (same passages, same order). Models run in parallel.
The cache is NOT used, so every model really answers.
Quality columns are automatic heuristics (faithfulness to the passages,
citation count, optional similarity to a reference answer you provide).
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from sqlalchemy.orm import Session

from app.analytics.events import emit
from app.core.config import get_settings
from app.core.errors import AppError
from app.embeddings import Embedder
from app.evaluation import quality
from app.llm.base import LLMError, LLMRequest, drain
from app.llm.registry import ModelRegistry, compute_cost
from app.models import Comparison, LLMCall
from app.rag.prompt import SYSTEM_PROMPT, build_user_message
from app.rag.service import DocumentService
from app.rag.vector_store import VectorStore
from app.services.runtime_settings import get_runtime


def run_comparison(db: Session, store: VectorStore, embedder: Embedder, registry: ModelRegistry, tenant: str,
                   query: str, model_ids: list[str], document_ids: list[int] | None,
                   reference_answer: str | None = None) -> Comparison:
    s = get_settings()
    q = " ".join(query.split())
    if not q:
        raise AppError("The question is empty.", 422, "empty_query")
    available = {m.id: m for m in registry.available(db)}
    unknown = [m for m in model_ids if m not in available]
    if unknown:
        raise AppError(f"Not available right now: {', '.join(unknown)}", 422, "model_unavailable")
    if not 1 <= len(model_ids) <= 6:
        raise AppError("Choose between 1 and 6 models.", 422, "bad_model_count")

    rt = get_runtime(db)
    docs = DocumentService(db, store, embedder)
    ids = docs.indexed_ids(tenant, document_ids)
    vector = embedder.embed([q])[0]
    chunks = docs.retrieve(tenant, vector, ids, int(rt["retrieval_top_k"]), float(rt["min_retrieval_score"]))
    if not chunks:
        raise AppError("No relevant passages were found in the selected documents, so there is nothing to compare.",
                       422, "no_context")
    user = build_user_message(q, chunks)
    mock_ctx = [{"index": i, "text": c.text} for i, c in enumerate(chunks, start=1)]
    ctx_texts = [c.text for c in chunks]

    def call(mid: str) -> dict:
        m = available[mid]
        t0 = time.perf_counter()
        try:
            text, usage = drain(registry.provider(m.provider).stream(LLMRequest(
                model=m.model_name, system=SYSTEM_PROMPT, user=user, max_output_tokens=s.llm_max_output_tokens,
                timeout_s=s.llm_timeout_seconds, effort=m.effort, mock_context=mock_ctx)))
            return {"model": m, "text": text.strip(), "usage": usage, "ms": (time.perf_counter() - t0) * 1000}
        except LLMError as e:
            return {"model": m, "error": e.kind, "message": str(e), "ms": (time.perf_counter() - t0) * 1000}

    with ThreadPoolExecutor(max_workers=len(model_ids)) as pool:
        raw = list(pool.map(call, model_ids))

    ref_vec = embedder.embed([reference_answer])[0] if reference_answer else None
    results = []
    for r in raw:
        m = r["model"]
        if "error" in r:
            db.add(LLMCall(provider=m.provider, model=m.model_name, tenant_id=tenant, purpose="compare", success=False,
                           error_type=r["error"], latency_ms=r["ms"], is_mock=m.is_mock, usage_source="none"))
            results.append({"model_id": m.id, "model": m.display_name, "provider": m.provider, "tier": m.tier,
                            "error": r["message"], "latency_ms": round(r["ms"], 1)})
            continue
        u = r["usage"]
        cost, status = compute_cost(db, m.id, u.input_tokens, u.output_tokens)
        db.add(LLMCall(provider=m.provider, model=m.model_name, tenant_id=tenant, purpose="compare",
                       input_tokens=u.input_tokens, output_tokens=u.output_tokens, usage_source=u.source,
                       estimated_cost_usd=cost or 0.0, cost_status=status, latency_ms=r["ms"], is_mock=m.is_mock,
                       served_model=u.served_model))
        ref_sim = None
        if ref_vec is not None and r["text"]:
            a = embedder.embed([r["text"]])[0]
            ref_sim = round(float(np.dot(a, ref_vec) / ((np.linalg.norm(a) * np.linalg.norm(ref_vec)) or 1)), 4)
        results.append({
            "model_id": m.id, "model": m.display_name, "provider": m.provider, "tier": m.tier, "is_mock": m.is_mock,
            "answer": r["text"], "latency_ms": round(r["ms"], 1), "input_tokens": u.input_tokens,
            "output_tokens": u.output_tokens, "usage_source": u.source, "cost_usd": cost, "cost_status": status,
            "faithfulness": quality.faithfulness(r["text"], ctx_texts, embedder),
            "citations_used": quality.citation_count(r["text"]), "answer_chars": len(r["text"]),
            "reference_similarity": ref_sim})
    comp = Comparison(tenant_id=tenant, query_text=q, document_ids=ids,
                      context=[c.citation(i) for i, c in enumerate(chunks, start=1)], results=results,
                      is_mock=any(r.get("is_mock") for r in results))
    db.add(comp)
    db.commit()
    emit(db, "comparison", f"Compared {len(model_ids)} model(s) on one question", tenant=tenant,
         data={"comparison_id": comp.id, "models": model_ids})
    return comp


def comparison_report(c: Comparison) -> str:
    lines = [f"# NEXUS AI model comparison #{c.id}", "", f"**Question:** {c.query_text}", "",
             f"Created: {c.created_at.isoformat()}" + ("  \n**TEST MODE - mock answers, simulated costs**" if c.is_mock else ""),
             "", "All models received the identical retrieved context:", ""]
    for ctx in c.context or []:
        lines.append(f"* [{ctx['index']}] {ctx['filename']}" + (f" p.{ctx['page']}" if ctx.get("page") else "")
                     + f" (score {ctx['score']})")
    lines += ["", "| Model | Latency (ms) | Input tok | Output tok | Usage | Cost (USD) | Faithfulness | Citations |",
              "|---|---|---|---|---|---|---|---|"]
    for r in c.results:
        if "error" in r:
            lines.append(f"| {r['model']} | {r['latency_ms']} | - | - | - | - | failed: {r['error']} | - |")
        else:
            cost = "unpriced" if r["cost_usd"] is None else f"{r['cost_usd']:.6f} ({r['cost_status']})"
            lines.append(f"| {r['model']} | {r['latency_ms']} | {r['input_tokens']} | {r['output_tokens']} | "
                         f"{r['usage_source']} | {cost} | {r['faithfulness']} | {r['citations_used']} |")
    for r in c.results:
        if "answer" in r:
            lines += ["", f"## {r['model']}", "", r["answer"]]
    return "\n".join(lines) + "\n"
