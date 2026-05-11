import pytest

from trading_assistant.db.schema import SCHEMA_VERSION, create_schema, current_version


EXPECTED_TABLES = {
    "schema_version",
    "app_state",
    "job_locks",
    "audit_log",
    "signals",
    "trade_intents",
    "paper_orders",
    "fills",
    "news_items",
    "econ_observations",
}


def test_create_schema_is_idempotent(db_conn):
    create_schema(db_conn)
    create_schema(db_conn)  # second call must not raise
    rows = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {r["name"] for r in rows}
    assert EXPECTED_TABLES.issubset(names)


def test_create_schema_records_version(db_conn):
    create_schema(db_conn)
    assert current_version(db_conn) == SCHEMA_VERSION


def test_audit_log_is_append_only_in_practice(db_conn):
    create_schema(db_conn)
    db_conn.execute(
        "INSERT INTO audit_log(kind, payload_json) VALUES (?, ?)",
        ("test", '{"foo": 1}'),
    )
    row = db_conn.execute("SELECT id, kind FROM audit_log").fetchone()
    assert row["kind"] == "test"
    cols = {c["name"] for c in db_conn.execute("PRAGMA table_info(audit_log)").fetchall()}
    assert cols == {"id", "kind", "payload_json", "created_at"}


def test_app_state_seeded_with_defaults(db_conn):
    create_schema(db_conn)
    rows = {r["key"]: r["value"] for r in db_conn.execute("SELECT key, value FROM app_state")}
    assert rows["kill_switch"] == "off"
    assert rows["mode"] == "paper"


def test_job_locks_unique_on_name(db_conn):
    create_schema(db_conn)
    db_conn.execute("INSERT INTO job_locks(name, acquired_at) VALUES (?, ?)", ("scan", "t1"))
    with pytest.raises(Exception):
        db_conn.execute("INSERT INTO job_locks(name, acquired_at) VALUES (?, ?)", ("scan", "t2"))
