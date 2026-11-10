"""Pydantic schemas = the exact JSON shapes the API sends and receives."""
from datetime import datetime

from pydantic import BaseModel


class ComponentHealth(BaseModel):
    status: str          # "ok" | "error" | "not_configured" | "pending"
    detail: str = ""


class HealthResponse(BaseModel):
    status: str          # "ok" if every required component is ok, else "degraded"
    app: str
    version: str
    environment: str
    timestamp: datetime
    uptime_seconds: float
    components: dict[str, ComponentHealth]
    llm_providers: dict[str, bool]   # True = key/URL configured. Keys themselves are NEVER returned.
    mock_mode: bool
