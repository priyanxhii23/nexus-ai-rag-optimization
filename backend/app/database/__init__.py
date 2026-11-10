"""Database engine, session factory and table creation."""
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Every table class inherits from this."""


def make_engine(url: str):
    engine = create_engine(url, connect_args={"check_same_thread": False})

    # SQLite needs foreign keys switched on per connection.
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


settings = get_settings()
settings.resolve(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(bind=None) -> None:
    """Create all tables that don't exist yet (safe to run on every start)."""
    from app import models  # noqa: F401  (import registers the tables)

    Base.metadata.create_all(bind=bind or engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
