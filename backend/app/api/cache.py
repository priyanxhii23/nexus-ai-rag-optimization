"""Semantic cache administration + threshold optimizer."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.analytics.events import emit
from app.analytics.metrics import cache_stats
from app.api.deps import embedder_dep, store_dep
from app.cache.semantic_cache import SemanticCache
from app.core.errors import AppError
from app.core.security import tenant_id
from app.database import get_db
from app.evaluation.datasets import load_dataset
from app.evaluation.threshold import run_threshold_experiment
from app.models import CacheEntry, Document, RequestLog
from app.schemas import ThresholdExperimentRequest
from app.services.runtime_settings import get_runtime

router = APIRouter(prefix="/cache", tags=["cache"])


def _entry(e: CacheEntry, db: Session, full: bool = False) -> dict:
    docs = []
    for doc_id, ver in (e.source_versions or {}).items():
        d = db.get(Document, int(doc_id))
        docs.append({"document_id": int(doc_id), "version": ver, "filename": d.filename if d else None,
                     "current_version": d.version if d else None, "exists": d is not None})
    out = {"id": e.id, "query_text": e.query_text, "status": e.status, "invalidated_reason": e.invalidated_reason,
           "intent_category": e.intent_category, "scope_key": e.scope_key, "documents": docs, "model": e.model,
           "provider": e.provider, "is_mock": bool(e.is_mock), "original_cost_usd": e.original_cost_usd,
           "original_latency_ms": e.original_latency_ms, "input_tokens": e.input_tokens,
           "output_tokens": e.output_tokens, "hit_count": e.hit_count, "last_similarity": e.last_similarity,
           "last_hit_at": e.last_hit_at.isoformat() if e.last_hit_at else None,
           "created_at": e.created_at.isoformat(), "expires_at": e.expires_at.isoformat(),
           "response_preview": e.response_text[:240]}
    if full:
        out["response_text"] = e.response_text
        out["citations"] = e.citations or []
        hits = db.scalars(select(RequestLog).where(RequestLog.cache_entry_id == e.id,
                                                   RequestLog.cache_status.in_(["exact_hit", "semantic_hit"]))
                          .order_by(RequestLog.created_at.desc()).limit(50))
        out["hit_history"] = [{"request_id": r.id, "query_text": r.query_text, "status": r.cache_status,
                               "similarity": r.similarity, "reason": r.cache_reason,
                               "created_at": r.created_at.isoformat()} for r in hits]
    return out


@router.get("/stats")
def stats(db: Session = Depends(get_db), tenant: str = Depends(tenant_id)):
    SemanticCache(db, None).expire_stale(tenant)  # type: ignore[arg-type]
    return {**cache_stats(db, tenant), "settings": {k: v for k, v in get_runtime(db).items()
                                                    if k in ("cache_enabled", "similarity_threshold", "cache_ttl_hours")}}


@router.get("/entries")
def entries(search: str | None = Query(None, max_length=200), status: str | None = None,
            limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db),
            tenant: str = Depends(tenant_id)):
    SemanticCache(db, None).expire_stale(tenant)  # type: ignore[arg-type]
    q = select(CacheEntry).where(CacheEntry.tenant_id == tenant)
    if status:
        q = q.where(CacheEntry.status == status)
    if search:
        like = f"%{search.strip()}%"
        q = q.where(or_(CacheEntry.query_text.ilike(like), CacheEntry.response_text.ilike(like)))
    total = len(list(db.scalars(q)))
    rows = db.scalars(q.order_by(CacheEntry.created_at.desc()).offset(offset).limit(limit))
    return {"total": total, "entries": [_entry(e, db) for e in rows]}


@router.get("/entries/{entry_id}")
def entry(entry_id: int, db: Session = Depends(get_db), tenant: str = Depends(tenant_id)):
    e = db.get(CacheEntry, entry_id)
    if e is None or e.tenant_id != tenant:
        raise AppError("Cache entry not found.", 404, "not_found")
    return _entry(e, db, full=True)


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: int, db: Session = Depends(get_db), tenant: str = Depends(tenant_id),
                 store=Depends(store_dep)):
    e = db.get(CacheEntry, entry_id)
    if e is None or e.tenant_id != tenant:
        raise AppError("Cache entry not found.", 404, "not_found")
    SemanticCache(db, store).delete_entry(e)
    emit(db, "cache_deleted", f"Cache entry {entry_id} deleted", tenant=tenant)
    return {"deleted": entry_id}


@router.delete("")
def clear(db: Session = Depends(get_db), tenant: str = Depends(tenant_id), store=Depends(store_dep)):
    n = SemanticCache(db, store).clear(tenant)
    emit(db, "cache_cleared", f"Cache cleared ({n} entries)", tenant=tenant)
    return {"deleted": n}


@router.post("/threshold-experiment")
def threshold_experiment(body: ThresholdExperimentRequest, db: Session = Depends(get_db),
                         tenant: str = Depends(tenant_id), embedder=Depends(embedder_dep)):
    try:
        ds = load_dataset(body.dataset)
    except KeyError:
        raise AppError("Unknown dataset.", 404, "not_found")
    st = cache_stats(db, tenant)
    return run_threshold_experiment(ds["pairs"], embedder, st["avg_hit_latency_ms"], st["avg_miss_latency_ms"],
                                    float(get_runtime(db)["similarity_threshold"]))
