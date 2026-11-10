"""FastAPI entry point.  Run with:  uvicorn app.main:app --reload   (from the backend folder)

Swagger UI: http://localhost:8000/docs
"""
import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.analytics.events import emit
from app.api import benchmarks, cache, compare, documents, health, metrics, models, monitoring, query, settings as settings_api
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import get_logger, request_id_var, setup_logging
from app.core.security import RateLimiter
from app.database import SessionLocal, configure_engine, init_db
from app.embeddings import get_embedder
from app.llm.registry import seed_models

settings = get_settings()
setup_logging(settings.log_level, settings.resolve(settings.logs_path) if settings.app_env != "test" else None)
log = get_logger("app")
_limiter = RateLimiter(settings.rate_limit_per_minute)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    if not getattr(app.state, "skip_startup", False):   # tests configure their own database
        s.ensure_directories()
        configure_engine()
    init_db()
    db = SessionLocal()
    try:
        seed_models(db)
        emit(db, "startup", f"{s.app_name} v{s.app_version} started"
             + (" in TEST MODE (mock LLM)" if s.mock_mode else ""), tenant=None,
             data={"providers": s.provider_status, "mock_mode": s.mock_mode})
    finally:
        db.close()
    if not getattr(app.state, "skip_startup", False):
        # load the embedding model in the background so the first question is fast
        threading.Thread(target=get_embedder().warm_up, daemon=True, name="embedding-warmup").start()
    log.info("%s v%s started (env=%s, mock_mode=%s)", s.app_name, s.app_version, s.app_env, s.mock_mode)
    yield
    log.info("Shutting down")


app = FastAPI(
    title="NEXUS AI API",
    version=settings.app_version,
    description="Intelligent RAG optimisation and cost-aware model orchestration. "
                "Every response is computed from real data; mock (test-mode) output is always labelled.",
    lifespan=lifespan,
)

# Only our own frontend may call this API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted({settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"}),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Tenant-ID", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    rid = "".join(ch for ch in rid if ch.isalnum() or ch in "-_")[:40] or uuid.uuid4().hex[:12]
    token = request_id_var.set(rid)
    t0 = time.perf_counter()
    try:
        path = request.url.path
        # request size guard (uploads are additionally checked per file)
        max_body = (settings.max_upload_mb * 20 + 1) * 1_000_000
        if int(request.headers.get("content-length") or 0) > max_body:
            return JSONResponse({"error": {"code": "payload_too_large", "message": "Request is too large.",
                                           "request_id": rid}}, status_code=413)
        # rate limit state-changing calls per client
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and path.startswith("/api/"):
            client = request.client.host if request.client else "unknown"
            if not _limiter.check(client):
                return JSONResponse({"error": {"code": "rate_limited", "message": "Too many requests - slow down.",
                                               "request_id": rid}}, status_code=429, headers={"Retry-After": "60"})
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if not path.startswith(("/api/monitoring", "/api/health")):
            log.info("%s %s -> %s (%.0f ms)", request.method, path, response.status_code, (time.perf_counter() - t0) * 1000)
        return response
    finally:
        request_id_var.reset(token)


install_error_handlers(app)
for r in (health.router, metrics.router, documents.router, query.router, cache.router, models.router,
          compare.router, benchmarks.router, monitoring.router, settings_api.router):
    app.include_router(r, prefix="/api")


@app.get("/", include_in_schema=False)
def root():
    return {"message": "NEXUS AI API is running", "docs": "/docs", "health": "/api/health"}
