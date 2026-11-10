"""Pydantic schemas = the exact JSON shapes the API receives (and key responses)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ComponentHealth(BaseModel):
    status: str          # "ok" | "error" | "not_configured" | "pending" | "loading"
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
    models_available: int


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=20000)
    document_ids: list[int] | None = Field(default=None, max_length=200)
    model_id: str | None = Field(default=None, max_length=120)
    mode: Literal["baseline", "cache", "optimized"] = "optimized"
    conversation_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("query")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("query must not be blank")
        return v


class AnalyzeRequest(BaseModel):
    query: str = Field(min_length=1, max_length=20000)
    model_id: str | None = None
    has_documents: bool = True


class CompareRequest(BaseModel):
    query: str = Field(min_length=1, max_length=20000)
    model_ids: list[str] = Field(min_length=1, max_length=6)
    document_ids: list[int] | None = None
    reference_answer: str | None = Field(default=None, max_length=10000)


class SettingsUpdate(BaseModel):
    cache_enabled: bool | None = None
    similarity_threshold: float | None = Field(default=None, ge=0.5, le=1.0)
    cache_ttl_hours: int | None = Field(default=None, ge=1, le=24 * 365)
    routing_strategy: Literal["balanced", "cost_saver", "quality_first"] | None = None
    retrieval_top_k: int | None = Field(default=None, ge=1, le=20)
    min_retrieval_score: float | None = Field(default=None, ge=0.0, le=1.0)


class ModelUpdate(BaseModel):
    enabled: bool | None = None
    tier: Literal["small", "medium", "large"] | None = None
    input_price_per_mtok: float | None = Field(default=None, ge=0, le=10000)
    output_price_per_mtok: float | None = Field(default=None, ge=0, le=10000)
    price_source: str | None = Field(default=None, max_length=300)
    clear_prices: bool = False


class ModelCreate(BaseModel):
    provider: Literal["gemini", "openai_compatible"]
    model_name: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:/-]+$")
    tier: Literal["small", "medium", "large"]
    display_name: str | None = Field(default=None, max_length=120)
    input_price_per_mtok: float | None = Field(default=None, ge=0, le=10000)
    output_price_per_mtok: float | None = Field(default=None, ge=0, le=10000)
    price_source: str | None = Field(default=None, max_length=300)


class BenchmarkCreate(BaseModel):
    name: str = Field(default="Benchmark", max_length=200)
    dataset: str = Field(default="nexus_demo_v1", max_length=100)
    configs: list[Literal["baseline", "cache", "optimized"]] = Field(default=["baseline", "cache", "optimized"],
                                                                     min_length=1, max_length=3)
    threshold: float | None = Field(default=None, ge=0.5, le=1.0)
    confirm_cost: bool = False   # must be true when real (paid) providers would be called


class ThresholdExperimentRequest(BaseModel):
    dataset: str = Field(default="nexus_demo_v1", max_length=100)
