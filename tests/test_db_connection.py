import sqlite3
from pathlib import Path

from trading_assistant.db.connection import open_connection


def test_open_connection_enables_wal_mode(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = open_connection(db_path)
    cur = conn.execute("PRAGMA journal_mode;")
    mode = cur.fetchone()[0]
    assert mode.lower() == "wal"
    conn.close()


def test_open_connection_enables_foreign_keys(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = open_connection(db_path)
    cur = conn.execute("PRAGMA foreign_keys;")
    assert cur.fetchone()[0] == 1
    conn.close()


def test_open_connection_returns_row_factory_dict(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = open_connection(db_path)
    conn.execute("CREATE TABLE t (a INTEGER, b TEXT)")
    conn.execute("INSERT INTO t VALUES (1, 'x')")
    row = conn.execute("SELECT * FROM t").fetchone()
    assert row["a"] == 1
    assert row["b"] == "x"
    conn.close()


def test_open_connection_creates_parent_dir(tmp_path: Path):
    db_path = tmp_path / "nested" / "dir" / "test.db"
    conn = open_connection(db_path)
    assert db_path.parent.is_dir()
    assert isinstance(conn, sqlite3.Connection)
    conn.close()
