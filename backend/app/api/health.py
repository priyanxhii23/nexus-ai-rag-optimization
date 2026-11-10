import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.api.deps import embedder_dep, registry_dep, store_dep
from app.core.config import get_settings
from app.database import get_db
from app.schemas import ComponentHealth, HealthResponse

router = APIRouter(tags=["system"])
STARTED_AT = time.monotonic()


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db), store=Depends(store_dep), embedder=Depends(embedder_dep),
           registry=Depends(registry_dep)) -> HealthResponse:
    s = get_settings()
    components: dict[str, ComponentHealth] = {}

    try:   # real check: query SQLite and list the tables
        db.execute(text("SELECT 1"))
        tables = inspect(db.get_bind()).get_table_names()
        components["database"] = ComponentHealth(status="ok", detail=f"SQLite, {len(tables)} tables")
    except Exception as exc:  # noqa: BLE001
        components["database"] = ComponentHealth(status="error", detail=type(exc).__name__)

    try:
        counts = store.count()
        components["vector_store"] = ComponentHealth(
            status="ok", detail=f"ChromaDB, {counts['doc_chunks']} chunk vectors, {counts['query_cache']} cache vectors")
    except Exception as exc:  # noqa: BLE001
        components["vector_store"] = ComponentHealth(status="error", detail=type(exc).__name__)

    if getattr(embedder, "loaded", False):
        detail = f"{embedder.name} ({embedder.dim} dims)"
        if getattr(embedder, "load_seconds", None):
            detail += f", loaded in {embedder.load_seconds}s"
        components["embeddings"] = ComponentHealth(status="ok", detail=detail)
    elif getattr(embedder, "load_error", None):
        components["embeddings"] = ComponentHealth(status="error", detail=embedder.load_error)
    else:
        components["embeddings"] = ComponentHealth(status="loading", detail="Model is loading in the background")

    available = registry.available(db)
    components["llm"] = ComponentHealth(
        status="ok" if available else "error",
        detail=("TEST MODE - mock provider (answers are not real LLM output)" if s.mock_mode
                else f"{len(available)} model(s) available") if available else "No model available")

    required = ("database", "vector_store", "embeddings", "llm")
    overall = "ok" if all(components[k].status in ("ok", "loading") for k in required) else "degraded"
    return HealthResponse(status=overall, app=s.app_name, version=s.app_version, environment=s.app_env,
                          timestamp=datetime.now(timezone.utc), uptime_seconds=round(time.monotonic() - STARTED_AT, 2),
                          components=components, llm_providers=s.provider_status, mock_mode=s.mock_mode,
                          models_available=len(available))
