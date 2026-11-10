"""Overview metrics — computed from the real request_logs / llm_calls tables.

On a fresh install every value is None/0 and `has_data` is False, so the
frontend shows an empty state instead of invented numbers.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DEFAULT_TENANT, LLMCall, RequestLog

router = APIRouter(prefix="/metrics", tags=["analytics"])


class ActivityItem(BaseModel):
    id: int
    query_text: str
    cache_status: str
    total_latency_ms: float
    created_at: str


class OverviewMetrics(BaseModel):
    has_data: bool
    total_queries: int
    cache_hit_rate: float | None          # 0..1
    avg_latency_ms: float | None
    estimated_cost_usd: float             # always an ESTIMATE unless usage_source == "provider"
    llm_calls: int
    llm_calls_avoided: int                # = cache hits
    recent_activity: list[ActivityItem]


@router.get("/overview", response_model=OverviewMetrics)
def overview(db: Session = Depends(get_db)) -> OverviewMetrics:
    t = DEFAULT_TENANT
    total = db.scalar(select(func.count()).select_from(RequestLog).where(RequestLog.tenant_id == t)) or 0
    hits = db.scalar(
        select(func.count()).select_from(RequestLog)
        .where(RequestLog.tenant_id == t, RequestLog.cache_status.in_(["exact_hit", "semantic_hit"]))
    ) or 0
    avg_latency = db.scalar(select(func.avg(RequestLog.total_latency_ms)).where(RequestLog.tenant_id == t))
    calls_q = select(func.count(LLMCall.id), func.coalesce(func.sum(LLMCall.estimated_cost_usd), 0.0)) \
        .join(RequestLog, LLMCall.request_id == RequestLog.id).where(RequestLog.tenant_id == t)
    calls, cost = db.execute(calls_q).one()
    recent = db.scalars(
        select(RequestLog).where(RequestLog.tenant_id == t).order_by(RequestLog.created_at.desc()).limit(8)
    ).all()

    return OverviewMetrics(
        has_data=total > 0,
        total_queries=total,
        cache_hit_rate=(hits / total) if total else None,
        avg_latency_ms=round(avg_latency, 1) if avg_latency is not None else None,
        estimated_cost_usd=round(float(cost), 6),
        llm_calls=calls,
        llm_calls_avoided=hits,
        recent_activity=[
            ActivityItem(id=r.id, query_text=r.query_text, cache_status=r.cache_status,
                         total_latency_ms=r.total_latency_ms, created_at=r.created_at.isoformat())
            for r in recent
        ],
    )
