"""Database engine, session factory, schema creation and additive migrations.

* The engine is created lazily (no side effects at import time), so tests can
  point the whole app at a throw-away database with `configure_engine(url)`.
* `init_db()` creates missing tables AND adds missing columns to existing
  tables. That keeps a database created by an older NEXUS AI version working
  after an upgrade (SQLAlchemy's create_all alone never adds columns).
"""
from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.logging import get_logger

log = get_logger("database")
SCHEMA_VERSION = 4


class Base(DeclarativeBase):
    """Every table class inherits from this."""


_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def make_engine(url: str) -> Engine:
    kwargs = {"connect_args": {"check_same_thread": False, "timeout": 30}}
    engine = create_engine(url, **kwargs)

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        if url not in ("sqlite://", "sqlite:///:memory:"):
            cur.execute("PRAGMA journal_mode=WAL")   # readers don't block the writer
        cur.close()

    return engine


def configure_engine(url: str | None = None) -> Engine:
    """(Re)create the global engine. Called at startup and by tests."""
    global _engine, _SessionLocal
    from app.core.config import get_settings

    if _engine is not None:
        _engine.dispose()
    settings = get_settings()
    if url is None:
        settings.ensure_directories()
        url = settings.database_url
    _engine = make_engine(url)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    return _engine if _engine is not None else configure_engine()


def SessionLocal() -> Session:  # noqa: N802 - keeps the familiar name
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal()


def _add_missing_columns(engine: Engine) -> list[str]:
    """Additive migration: ALTER TABLE ... ADD COLUMN for columns the model has but the DB lacks."""
    added: list[str] = []
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                col_type = col.type.compile(dialect=engine.dialect)
                default_sql = ""
                if col.server_default is not None:
                    default_sql = f" DEFAULT {col.server_default.arg}"
                elif col.default is not None and getattr(col.default, "is_scalar", False):
                    val = col.default.arg
                    if isinstance(val, bool):
                        default_sql = f" DEFAULT {int(val)}"
                    elif isinstance(val, (int, float)):
                        default_sql = f" DEFAULT {val}"
                    elif isinstance(val, str):
                        default_sql = " DEFAULT '" + val.replace("'", "''") + "'"
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type}{default_sql}'))
                added.append(f"{table.name}.{col.name}")
    return added


def init_db(engine: Engine | None = None) -> None:
    """Create tables, add missing columns, record schema version. Safe on every start."""
    from app import models  # noqa: F401  (import registers the tables)

    engine = engine or get_engine()
    Base.metadata.create_all(bind=engine)
    added = _add_missing_columns(engine)
    if added:
        log.info("Schema upgraded, added columns: %s", ", ".join(added))
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT)"))
        conn.execute(text("INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', :v)"),
                     {"v": str(SCHEMA_VERSION)})


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
