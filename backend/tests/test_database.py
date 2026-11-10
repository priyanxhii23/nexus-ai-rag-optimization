"""Database initialisation, additive migration from v3.1, persistence."""
import sqlite3

from sqlalchemy import inspect

from app.database import SessionLocal, configure_engine, init_db
from app.models import RequestLog

V31_SCHEMA = """
CREATE TABLE documents (id INTEGER PRIMARY KEY, tenant_id VARCHAR(64) NOT NULL, filename VARCHAR(255) NOT NULL,
  content_hash VARCHAR(64) NOT NULL, version INTEGER NOT NULL, size_bytes INTEGER NOT NULL, chunk_count INTEGER NOT NULL,
  status VARCHAR(20) NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL);
CREATE TABLE request_logs (id INTEGER PRIMARY KEY, tenant_id VARCHAR(64) NOT NULL, query_text TEXT NOT NULL,
  cache_status VARCHAR(20) NOT NULL, similarity FLOAT, complexity VARCHAR(20), total_latency_ms FLOAT NOT NULL,
  error TEXT, created_at DATETIME NOT NULL);
CREATE TABLE llm_calls (id INTEGER PRIMARY KEY, request_id INTEGER REFERENCES request_logs(id), provider VARCHAR(40) NOT NULL,
  model VARCHAR(100) NOT NULL, input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL, usage_source VARCHAR(20) NOT NULL,
  estimated_cost_usd FLOAT NOT NULL, latency_ms FLOAT NOT NULL, created_at DATETIME NOT NULL);
INSERT INTO request_logs (tenant_id, query_text, cache_status, total_latency_ms, created_at)
  VALUES ('local', 'old question', 'miss', 12.5, '2026-11-01 10:00:00');
"""


def test_upgrades_a_v31_database_without_losing_data(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript(V31_SCHEMA)
    con.close()

    engine = configure_engine(f"sqlite:///{path.as_posix()}")
    init_db(engine)
    init_db(engine)   # idempotent

    cols = {c["name"] for c in inspect(engine).get_columns("request_logs")}
    assert {"cost_usd", "mode", "cache_entry_id", "analysis"} <= cols
    assert "cache_entries" in inspect(engine).get_table_names()
    db = SessionLocal()
    old = db.query(RequestLog).one()
    assert old.query_text == "old question" and old.total_latency_ms == 12.5
    assert old.mode == "optimized" and old.cost_usd == 0.0   # defaults filled for old rows
    db.close()
    engine.dispose()


def test_data_persists_across_restart(tmp_path):
    url = f"sqlite:///{(tmp_path / 'p.db').as_posix()}"
    init_db(configure_engine(url))
    db = SessionLocal()
    db.add(RequestLog(query_text="persist me"))
    db.commit()
    db.close()
    engine = configure_engine(url)        # simulates an application restart
    db = SessionLocal()
    assert db.query(RequestLog).filter_by(query_text="persist me").count() == 1
    db.close()
    engine.dispose()


def test_tests_do_not_touch_real_database(env):
    from app.core.config import PROJECT_ROOT
    assert str(PROJECT_ROOT / "data" / "nexus.db") not in env.settings.database_url
