"""FastAPI entry point.  Run with:  uvicorn app.main:app --reload"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.database import init_db

settings = get_settings()
setup_logging(settings.log_level)
log = logging.getLogger("nexus")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    log.info("%s v%s started (env=%s, db=%s)", settings.app_name, settings.app_version,
             settings.app_env, settings.sqlite_path)
    yield
    log.info("Shutting down")


app = FastAPI(
    title="NEXUS AI API",
    version=settings.app_version,
    description="RAG optimisation & cost-aware model orchestration",
    lifespan=lifespan,
)

# Only our own frontend may call this API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")


@app.get("/")
def root():
    return {"message": "NEXUS AI API is running", "docs": "/docs", "health": "/api/health"}
