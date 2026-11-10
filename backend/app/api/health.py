import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import get_db
from app.schemas import ComponentHealth, HealthResponse

router = APIRouter(tags=["system"])
STARTED_AT = time.monotonic()


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    s = get_settings()
    components: dict[str, ComponentHealth] = {}

    # Real check: run a query against SQLite and list the tables.
    try:
        db.execute(text("SELECT 1"))
        tables = sorted(inspect(db.get_bind()).get_table_names())
        components["database"] = ComponentHealth(status="ok", detail=f"SQLite, tables: {', '.join(tables)}")
    except Exception as exc:  # noqa: BLE001
        components["database"] = ComponentHealth(status="error", detail=type(exc).__name__)

    # Honest placeholders for parts that don't exist yet.
    components["vector_store"] = ComponentHealth(status="pending", detail="ChromaDB arrives in Milestone 4")
    components["embeddings"] = ComponentHealth(status="pending", detail="MiniLM arrives in Milestone 4")

    providers = {
        "anthropic": bool(s.anthropic_api_key),
        "gemini": bool(s.gemini_api_key),
        "openai_compatible": bool(s.openai_compat_base_url),
    }

    overall = "ok" if components["database"].status == "ok" else "degraded"
    return HealthResponse(
        status=overall,
        app=s.app_name,
        version=s.app_version,
        environment=s.app_env,
        timestamp=datetime.now(timezone.utc),
        uptime_seconds=round(time.monotonic() - STARTED_AT, 2),
        components=components,
        llm_providers=providers,
        mock_mode=s.llm_mock_mode,
    )
