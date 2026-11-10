"""Model configuration + routing analytics."""
from dataclasses import asdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.events import emit
from app.api.deps import registry_dep
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import tenant_id
from app.database import get_db
from app.llm.registry import model_id
from app.models import ModelConfig, RequestLog
from app.router.model_router import STRATEGY_TIERS
from app.schemas import ModelCreate, ModelUpdate

router = APIRouter(tags=["models"])


@router.get("/models")
def list_models(db: Session = Depends(get_db), registry=Depends(registry_dep)):
    s = get_settings()
    return {"mock_mode": s.mock_mode, "providers": s.provider_status,
            "models": [asdict(m) for m in registry.models(db)], "strategies": STRATEGY_TIERS}


@router.patch("/models/{mid:path}")
def update_model(mid: str, body: ModelUpdate, db: Session = Depends(get_db)):
    m = db.get(ModelConfig, mid)
    if m is None:
        raise AppError("Model not found.", 404, "not_found")
    if body.enabled is not None:
        m.enabled = body.enabled
    if body.tier is not None:
        m.tier = body.tier
    if body.clear_prices:
        m.input_price_per_mtok = m.output_price_per_mtok = None
        m.price_source = "Not set"
    if body.input_price_per_mtok is not None or body.output_price_per_mtok is not None:
        if m.is_mock:
            raise AppError("Mock models are priced by the real model they simulate.", 422, "mock_price")
        if body.input_price_per_mtok is None or body.output_price_per_mtok is None:
            raise AppError("Set both input and output prices.", 422, "incomplete_price")
        m.input_price_per_mtok, m.output_price_per_mtok = body.input_price_per_mtok, body.output_price_per_mtok
        m.price_source = body.price_source or "Entered by user in Settings"
    db.commit()
    emit(db, "model_updated", f"Model {mid} updated")
    return {"ok": True}


@router.post("/models", status_code=201)
def add_model(body: ModelCreate, db: Session = Depends(get_db)):
    mid = model_id(body.provider, body.model_name)
    if db.get(ModelConfig, mid):
        raise AppError("This model is already configured.", 409, "exists")
    priced = body.input_price_per_mtok is not None and body.output_price_per_mtok is not None
    db.add(ModelConfig(id=mid, provider=body.provider, model_name=body.model_name, tier=body.tier,
                       display_name=body.display_name or body.model_name,
                       input_price_per_mtok=body.input_price_per_mtok if priced else None,
                       output_price_per_mtok=body.output_price_per_mtok if priced else None,
                       price_source=(body.price_source or "Entered by user") if priced else "Not set"))
    db.commit()
    emit(db, "model_added", f"Model {mid} added")
    return {"id": mid}


@router.get("/models/discover/{provider}")
def discover(provider: str, registry=Depends(registry_dep)):
    """Ask the provider which models this API key can use (real list, not guessed)."""
    try:
        names = registry.provider(provider).list_models()
    except KeyError:
        raise AppError(f"{provider} is not configured in .env.", 400, "not_configured")
    return {"provider": provider, "models": sorted(names)}


@router.get("/router/decisions")
def decisions(limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db), tenant: str = Depends(tenant_id)):
    rows = db.scalars(select(RequestLog).where(RequestLog.tenant_id == tenant, RequestLog.routed_by.is_not(None))
                      .order_by(RequestLog.created_at.desc()).limit(limit))
    return [{"id": r.id, "query_text": r.query_text[:200], "category": r.category, "complexity": r.complexity,
             "complexity_score": r.complexity_score, "model": r.selected_model, "routed_by": r.routed_by,
             "reason": r.routing_reason, "fallback_used": bool(r.fallback_used), "latency_ms": r.total_latency_ms,
             "cost_usd": r.cost_usd, "cost_status": r.cost_status, "saved_by_routing_usd": r.saved_cost_routing,
             "created_at": r.created_at.isoformat()} for r in rows]
