"""Logging: console + rotating file (data/logs/nexus.log), with request IDs.

SECURITY: never log API keys, document text, questions or answers.
Log IDs, sizes, timings and status codes instead.
"""
import logging
import logging.handlers
from contextvars import ContextVar
from pathlib import Path

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | req=%(request_id)s | %(message)s"


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def setup_logging(level: str = "INFO", logs_dir: Path | None = None) -> None:
    """Configure the 'nexus' logger once (safe to call repeatedly)."""
    logger = logging.getLogger("nexus")
    if getattr(logger, "_nexus_configured", False):
        return
    logger.setLevel(level.upper())
    logger.propagate = False
    fmt, rid = logging.Formatter(_FORMAT), _RequestIdFilter()

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.addFilter(rid)
    logger.addHandler(console)

    if logs_dir is not None:
        logs_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            logs_dir / "nexus.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        fh.setFormatter(fmt)
        fh.addFilter(rid)
        logger.addHandler(fh)
    logger._nexus_configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"nexus.{name}")
