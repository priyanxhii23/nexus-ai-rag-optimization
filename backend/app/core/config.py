"""Central configuration.

All settings are read from environment variables / the project-root .env file.
Nothing secret is ever hard-coded here. Values that users may change at run
time (threshold, TTL, routing strategy) are only *defaults*: the live values
live in the `app_settings` table and are edited from the Settings page.
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[3] is the project root (nexus-ai/)
PROJECT_ROOT = Path(__file__).resolve().parents[3]

_PLACEHOLDERS = {"", "your-key-here", "changeme", "none", "null", "xxx"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "NEXUS AI"
    app_version: str = "0.4.0"
    app_env: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"
    frontend_origin: str = "http://localhost:5173"

    # ---------- Storage ----------
    sqlite_path: str = "data/nexus.db"
    chroma_path: str = "data/chroma"
    documents_path: str = "data/documents"
    models_cache_path: str = "data/models"
    logs_path: str = "data/logs"
    max_upload_mb: int = Field(default=20, ge=1, le=200)

    # ---------- Embeddings ----------
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ---------- Semantic cache defaults ----------
    cache_similarity_threshold: float = Field(default=0.92, ge=0.5, le=1.0)
    cache_ttl_hours: int = Field(default=72, ge=1, le=24 * 365)

    # ---------- RAG ----------
    chunk_size_chars: int = Field(default=900, ge=200, le=4000)
    chunk_overlap_chars: int = Field(default=150, ge=0, le=1000)
    retrieval_top_k: int = Field(default=5, ge=1, le=20)
    min_retrieval_score: float = Field(default=0.30, ge=0.0, le=1.0)

    # ---------- LLM providers ----------
    anthropic_api_key: str = ""
    anthropic_server_fallbacks: bool = True   # server-side refusal fallback on Opus/Sonnet 5.5

    gemini_api_key: str = ""
    # Gemini model IDs and prices are NOT guessed: set them from
    # https://ai.google.dev/gemini-api/docs/pricing (or pick in Settings).
    gemini_small_model: str = ""
    gemini_large_model: str = ""

    openai_compat_base_url: str = ""
    openai_compat_api_key: str = ""
    openai_compat_model: str = ""
    openai_compat_tier: Literal["small", "medium", "large"] = "small"
    openai_compat_input_price_per_mtok: float | None = None
    openai_compat_output_price_per_mtok: float | None = None

    # auto  -> mock answers only when no real provider is configured
    # true  -> always mock (tests / demos, no cost)
    # false -> never mock (requests fail clearly if no provider works)
    llm_mock_mode: Literal["auto", "true", "false"] = "auto"
    llm_timeout_seconds: int = Field(default=60, ge=5, le=600)
    llm_max_output_tokens: int = Field(default=8192, ge=256, le=64000)

    # ---------- Security ----------
    rate_limit_per_minute: int = Field(default=120, ge=10, le=10000)
    max_query_chars: int = Field(default=2000, ge=50, le=20000)

    @field_validator("anthropic_api_key", "gemini_api_key", "openai_compat_api_key", mode="before")
    @classmethod
    def _blank_placeholders(cls, v: object) -> str:
        s = str(v or "").strip()
        return "" if s.lower() in _PLACEHOLDERS else s

    @field_validator("llm_mock_mode", mode="before")
    @classmethod
    def _bool_to_mode(cls, v: object) -> str:
        s = str(v).strip().lower()
        return {"1": "true", "yes": "true", "on": "true", "0": "false", "no": "false", "off": "false"}.get(s, s or "auto")

    @field_validator("openai_compat_input_price_per_mtok", "openai_compat_output_price_per_mtok", mode="before")
    @classmethod
    def _empty_price(cls, v: object):
        return None if v is None or str(v).strip() == "" else v

    # ---------- Paths ----------
    def resolve(self, relative: str) -> Path:
        """Turn a project-relative path from .env into an absolute path."""
        p = Path(relative).expanduser()
        return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()

    @property
    def database_url(self) -> str:
        if self.sqlite_path == ":memory:":
            return "sqlite://"
        return f"sqlite:///{self.resolve(self.sqlite_path).as_posix()}"

    def ensure_directories(self) -> None:
        for p in (self.chroma_path, self.documents_path, self.models_cache_path, self.logs_path):
            self.resolve(p).mkdir(parents=True, exist_ok=True)
        if self.sqlite_path != ":memory:":
            self.resolve(self.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        (PROJECT_ROOT / "data" / "benchmarks").mkdir(parents=True, exist_ok=True)

    # ---------- Providers ----------
    @property
    def provider_status(self) -> dict[str, bool]:
        """True = credentials present. Keys themselves are NEVER returned."""
        return {
            "anthropic": bool(self.anthropic_api_key),
            "gemini": bool(self.gemini_api_key),
            "openai_compatible": bool(self.openai_compat_base_url and self.openai_compat_model),
        }

    @property
    def mock_mode(self) -> bool:
        if self.llm_mock_mode == "true":
            return True
        if self.llm_mock_mode == "false":
            return False
        return not any(self.provider_status.values())


@lru_cache
def get_settings() -> Settings:
    return Settings()
