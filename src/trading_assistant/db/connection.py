"""SQLite connection helpers. WAL mode is mandatory."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def open_connection(path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode and foreign keys enabled.

    Why WAL: the spec requires it because multiple cycle jobs and HTTP
    handlers will write concurrently in later phases. WAL avoids
    'database is locked' errors under modest contention.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None)  # autocommit
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn
