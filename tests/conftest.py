"""Shared pytest fixtures."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from trading_assistant.db.connection import open_connection


@pytest.fixture
def db_conn(tmp_path: Path) -> sqlite3.Connection:
    """A WAL-mode SQLite connection in a per-test tmp dir."""
    conn = open_connection(tmp_path / "test.db")
    yield conn
    conn.close()
