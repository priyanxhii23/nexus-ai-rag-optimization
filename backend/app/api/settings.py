from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics.events import emit
from app.core.config import get_settings
from app.core.errors import AppError
from app.database import get_db
from app.schemas import SettingsUpdate
from app.services.runtime_settings import ROUTING_STRATEGIES, defaults, get_runtime, update_runtime

router = APIRouter(prefix="/settings", tags=["settings"])


def _payload(db: Session) -> dict:
    s = get_settings()
    return {
        "runtime": get_runtime(db),
        "defaults": defaults(),
        "routing_strategies": list(ROUTING_STRATEGIES),
        "environment": {   # read-only, from .env - never includes secret values
            "app_env": s.app_env, "version": s.app_version, "embedding_model": s.embedding_model,
            "llm_mock_mode": s.llm_mock_mode, "mock_mode_active": s.mock_mode, "providers": s.provider_status,
            "max_upload_mb": s.max_upload_mb, "llm_timeout_seconds": s.llm_timeout_seconds,
            "rate_limit_per_minute": s.rate_limit_per_minute, "chunk_size_chars": s.chunk_size_chars,
            "chunk_overlap_chars": s.chunk_overlap_chars, "anthropic_server_fallbacks": s.anthropic_server_fallbacks,
            "gemini_models": {"small": s.gemini_small_model or None, "large": s.gemini_large_model or None},
            "openai_compatible": {"base_url_set": bool(s.openai_compat_base_url), "model": s.openai_compat_model or None},
        },
    }


@router.get("")
def read(db: Session = Depends(get_db)):
    return _payload(db)


@router.put("")
def write(body: SettingsUpdate, db: Session = Depends(get_db)):
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise AppError("Nothing to update.", 422, "empty_update")
    try:
        update_runtime(db, changes)
    except ValueError as e:
        raise AppError(str(e), 422, "invalid_setting")
    emit(db, "settings_updated", "Settings updated: " + ", ".join(f"{k}={v}" for k, v in changes.items()))
    return _payload(db)
