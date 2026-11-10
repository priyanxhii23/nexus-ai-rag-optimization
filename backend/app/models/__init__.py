"""SQLAlchemy table definitions.

Every table has a `tenant_id` column. Today there is one local user
("local"), but this boundary is what will stop one user's cached answers
from ever being served to another user.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

DEFAULT_TENANT = "local"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default=DEFAULT_TENANT, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)  # detects duplicate uploads
    version: Mapped[int] = mapped_column(Integer, default=1)          # bumps when a file is re-uploaded
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|indexed|failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RequestLog(Base):
    """One row per user question — the raw material for every dashboard chart."""
    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default=DEFAULT_TENANT, index=True)
    query_text: Mapped[str] = mapped_column(Text)
    cache_status: Mapped[str] = mapped_column(String(20), default="miss")  # exact_hit|semantic_hit|miss
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    complexity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    total_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    llm_calls: Mapped[list["LLMCall"]] = relationship(back_populates="request", cascade="all, delete-orphan")


class LLMCall(Base):
    """One row per actual provider call. Costs are labelled by their source."""
    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("request_logs.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    usage_source: Mapped[str] = mapped_column(String(20), default="estimated")  # provider|estimated|mock
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    request: Mapped[RequestLog | None] = relationship(back_populates="llm_calls")
