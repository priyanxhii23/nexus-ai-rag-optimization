"""SQLAlchemy table definitions.

Every user-facing table carries `tenant_id`. Today there is one local user
("local"), but this boundary is what guarantees one user's cached answers or
documents are never served to another user.

All new columns are nullable or have defaults so `init_db()` can add them to a
database created by an older version (additive migration).
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import DEFAULT_TENANT
from app.database import Base

__all__ = [
    "DEFAULT_TENANT", "utcnow", "Document", "DocumentChunk", "RequestLog", "LLMCall", "CacheEntry",
    "ModelConfig", "LatencyRecord", "CostRecord", "BenchmarkRun", "BenchmarkResult", "Comparison",
    "SystemEvent", "AppSetting",
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """SQLite has no time zones: store naive UTC, always return aware UTC.
    (Fixes timestamps being shown in the wrong time zone in the browser.)"""
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


# ============================================================ documents
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default=DEFAULT_TENANT, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)   # duplicate detection
    version: Mapped[int] = mapped_column(Integer, default=1)            # bumps on every update
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|indexed|failed
    file_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    stored_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    flagged_chunks: Mapped[int | None] = mapped_column(Integer, default=0)   # prompt-injection tripwire hits
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default=DEFAULT_TENANT, index=True)
    document_version: Mapped[int] = mapped_column(Integer, default=1)
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    flagged: Mapped[bool | None] = mapped_column(Boolean, default=False)
    vector_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

    document: Mapped[Document] = relationship(back_populates="chunks")


# ============================================================ requests & LLM calls
class RequestLog(Base):
    """One row per user question - the raw material for every dashboard chart."""
    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default=DEFAULT_TENANT, index=True)
    query_text: Mapped[str] = mapped_column(Text)
    cache_status: Mapped[str] = mapped_column(String(20), default="miss")  # exact_hit|semantic_hit|miss|bypass|error
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)  # best cache similarity seen
    complexity: Mapped[str | None] = mapped_column(String(20), nullable=True)  # simple|medium|complex
    total_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)

    source: Mapped[str | None] = mapped_column(String(20), default="playground")  # playground|benchmark|api
    mode: Mapped[str | None] = mapped_column(String(20), default="optimized")    # baseline|cache|optimized
    conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    benchmark_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    scope_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    document_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    complexity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    routed_by: Mapped[str | None] = mapped_column(String(10), nullable=True)   # auto|manual|baseline
    routing_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fallback_used: Mapped[bool | None] = mapped_column(Boolean, default=False)
    cache_entry_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_mock: Mapped[bool | None] = mapped_column(Boolean, default=False)
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    retrieval_count: Mapped[int | None] = mapped_column(Integer, default=0)
    top_retrieval_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int | None] = mapped_column(Integer, default=0)
    usage_source: Mapped[str | None] = mapped_column(String(20), nullable=True)   # provider|estimated|mock|none
    cost_usd: Mapped[float | None] = mapped_column(Float, default=0.0)            # estimated actual spend
    cost_status: Mapped[str | None] = mapped_column(String(20), nullable=True)    # priced|unpriced|simulated|none
    saved_cost_cache: Mapped[float | None] = mapped_column(Float, default=0.0)    # counterfactual
    saved_cost_routing: Mapped[float | None] = mapped_column(Float, default=0.0)  # counterfactual
    stage_timings: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    llm_calls: Mapped[list["LLMCall"]] = relationship(back_populates="request", cascade="all, delete-orphan")


class LLMCall(Base):
    """One row per actual provider call. Usage and cost are labelled by their source."""
    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("request_logs.id", ondelete="CASCADE"), nullable=True)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    usage_source: Mapped[str] = mapped_column(String(20), default="estimated")  # provider|estimated|mock
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    tenant_id: Mapped[str | None] = mapped_column(String(64), default=DEFAULT_TENANT, index=True)
    purpose: Mapped[str | None] = mapped_column(String(20), default="answer")   # answer|compare|benchmark
    success: Mapped[bool | None] = mapped_column(Boolean, default=True)
    error_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cost_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    served_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_mock: Mapped[bool | None] = mapped_column(Boolean, default=False)

    request: Mapped[RequestLog | None] = relationship(back_populates="llm_calls")


class LatencyRecord(Base):
    """Per-stage timing for each request (embedding, cache lookup, retrieval, llm, total)."""
    __tablename__ = "latency_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("request_logs.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(30))
    duration_ms: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class CostRecord(Base):
    """Cost ledger. `kind` separates real spend from counterfactual savings:
       actual          - estimated cost of an LLM call that really happened
       cache_saving    - estimated cost that WOULD have been paid without the cache
       routing_saving  - extra cost that WOULD have been paid on the baseline (large) model"""
    __tablename__ = "cost_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default=DEFAULT_TENANT, index=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("request_logs.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amount_usd: Mapped[float] = mapped_column(Float, default=0.0)
    basis: Mapped[str | None] = mapped_column(String(30), nullable=True)   # provider_tokens|estimated_tokens|simulated
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)


# ============================================================ semantic cache
class CacheEntry(Base):
    __tablename__ = "cache_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default=DEFAULT_TENANT, index=True)
    query_text: Mapped[str] = mapped_column(Text)
    normalized_query: Mapped[str] = mapped_column(Text)
    query_hash: Mapped[str] = mapped_column(String(64), index=True)   # exact-match key
    scope_key: Mapped[str] = mapped_column(String(64), index=True)    # which documents were in scope
    source_versions: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {doc_id: version} actually used
    intent_category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    response_text: Mapped[str] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_mock: Mapped[bool | None] = mapped_column(Boolean, default=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int | None] = mapped_column(Integer, default=0)
    original_cost_usd: Mapped[float | None] = mapped_column(Float, default=0.0)
    original_latency_ms: Mapped[float | None] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|invalidated|expired
    invalidated_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    last_hit_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    request_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)


# ============================================================ models & settings
class ModelConfig(Base):
    __tablename__ = "model_configs"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)   # "<provider>:<model>"
    provider: Mapped[str] = mapped_column(String(40))
    model_name: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(120))
    tier: Mapped[str] = mapped_column(String(10))   # small|medium|large
    input_price_per_mtok: Mapped[float | None] = mapped_column(Float, nullable=True)
    output_price_per_mtok: Mapped[float | None] = mapped_column(Float, nullable=True)
    long_context_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    long_input_price_per_mtok: Mapped[float | None] = mapped_column(Float, nullable=True)
    long_output_price_per_mtok: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    simulates: Mapped[str | None] = mapped_column(String(120), nullable=True)  # mock model priced like this real model
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    effort: Mapped[str | None] = mapped_column(String(10), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict | list | str | float | int | bool | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


# ============================================================ evaluation
class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default=DEFAULT_TENANT, index=True)
    name: Mapped[str] = mapped_column(String(200))
    dataset: Mapped[str] = mapped_column(String(100))
    configs: Mapped[list] = mapped_column(JSON)          # ["baseline","cache","optimized"]
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")   # queued|running|completed|failed
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)  # True when mock LLM answered
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    results: Mapped[list["BenchmarkResult"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class BenchmarkResult(Base):
    __tablename__ = "benchmark_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("benchmark_runs.id", ondelete="CASCADE"), index=True)
    config: Mapped[str] = mapped_column(String(20))
    question_id: Mapped[str] = mapped_column(String(40))
    question: Mapped[str] = mapped_column(Text)
    cache_status: Mapped[str] = mapped_column(String(20))
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    complexity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    llm_called: Mapped[bool] = mapped_column(Boolean, default=False)
    retrieval_hit: Mapped[float | None] = mapped_column(Float, nullable=True)
    correctness: Mapped[float | None] = mapped_column(Float, nullable=True)
    faithfulness: Mapped[float | None] = mapped_column(Float, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[BenchmarkRun] = relationship(back_populates="results")


class Comparison(Base):
    __tablename__ = "comparisons"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default=DEFAULT_TENANT, index=True)
    query_text: Mapped[str] = mapped_column(Text)
    document_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    context: Mapped[list | None] = mapped_column(JSON, nullable=True)
    results: Mapped[list] = mapped_column(JSON)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


# ============================================================ monitoring
class SystemEvent(Base):
    __tablename__ = "system_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), default=DEFAULT_TENANT, index=True)
    request_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(40), index=True)
    level: Mapped[str] = mapped_column(String(10), default="info")   # info|warning|error
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
