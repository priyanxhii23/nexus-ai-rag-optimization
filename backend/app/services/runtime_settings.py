"""Run-time settings stored in the `app_settings` table (edited on the Settings page).

.env supplies the defaults; values saved from the UI override them and survive restarts.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AppSetting

ROUTING_STRATEGIES = ("balanced", "cost_saver", "quality_first")


def defaults() -> dict[str, Any]:
    s = get_settings()
    return {
        "cache_enabled": True,
        "similarity_threshold": s.cache_similarity_threshold,
        "cache_ttl_hours": s.cache_ttl_hours,
        "routing_strategy": "balanced",
        "retrieval_top_k": s.retrieval_top_k,
        "min_retrieval_score": s.min_retrieval_score,
    }


VALIDATORS = {
    "cache_enabled": lambda v: isinstance(v, bool),
    "similarity_threshold": lambda v: isinstance(v, (int, float)) and 0.5 <= v <= 1.0,
    "cache_ttl_hours": lambda v: isinstance(v, int) and 1 <= v <= 24 * 365,
    "routing_strategy": lambda v: v in ROUTING_STRATEGIES,
    "retrieval_top_k": lambda v: isinstance(v, int) and 1 <= v <= 20,
    "min_retrieval_score": lambda v: isinstance(v, (int, float)) and 0.0 <= v <= 1.0,
}


def get_runtime(db: Session) -> dict[str, Any]:
    values = defaults()
    for row in db.query(AppSetting).filter(AppSetting.key.in_(list(values))):
        values[row.key] = row.value
    return values


def update_runtime(db: Session, changes: dict[str, Any]) -> dict[str, Any]:
    for k, v in changes.items():
        if k not in VALIDATORS or not VALIDATORS[k](v):
            raise ValueError(f"Invalid value for {k}: {v!r}")
        row = db.get(AppSetting, k)
        if row is None:
            db.add(AppSetting(key=k, value=v))
        else:
            row.value = v
    db.commit()
    return get_runtime(db)
