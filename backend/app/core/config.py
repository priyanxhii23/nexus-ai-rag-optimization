"""Central configuration.

All settings are read from environment variables / the project-root .env file.
Nothing secret is ever hard-coded here.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[3] is the project root (nexus-ai/)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "NEXUS AI"
    app_version: str = "0.2.0"
    app_env: str = "development"
    log_level: str = "INFO"
    frontend_origin: str = "http://localhost:5173"

    sqlite_path: str = "data/nexus.db"
    chroma_path: str = "data/chroma"
    documents_path: str = "data/documents"
    max_upload_mb: int = 20

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    cache_similarity_threshold: float = 0.92
    cache_ttl_hours: int = 72

    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    openai_compat_base_url: str = ""
    openai_compat_api_key: str = ""
    llm_mock_mode: bool = False

    def resolve(self, relative: str) -> Path:
        """Turn a project-relative path from .env into an absolute path."""
        p = Path(relative)
        return p if p.is_absolute() else PROJECT_ROOT / p

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.resolve(self.sqlite_path).as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
