"""Typed read/write helpers per table. Hand-rolled, no ORM."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Iterator


class JobLockHeld(Exception):
    """Raised when a job lock is already held by someone else."""


class AppStateRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM app_state WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def set(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO app_state(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


class AuditLogRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def write(self, kind: str, payload: dict) -> None:
        self._conn.execute(
            "INSERT INTO audit_log(kind, payload_json) VALUES (?, ?)",
            (kind, json.dumps(payload, separators=(",", ":"), sort_keys=True)),
        )


class JobLockRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @contextmanager
    def acquire(self, name: str, now: str) -> Iterator[None]:
        try:
            self._conn.execute(
                "INSERT INTO job_locks(name, acquired_at) VALUES (?, ?)",
                (name, now),
            )
        except sqlite3.IntegrityError as exc:
            raise JobLockHeld(name) from exc
        try:
            yield
        finally:
            self._conn.execute("DELETE FROM job_locks WHERE name = ?", (name,))


class NewsRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(
        self,
        *,
        url_hash: str,
        source: str,
        title: str,
        snippet: str | None,
        published_at: str | None,
        arrived_at: str,
    ) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO news_items"
            "(url_hash, source, title, snippet, published_at, arrived_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (url_hash, source, title, snippet, published_at, arrived_at),
        )

    def fresh_since(self, iso_timestamp: str) -> Iterator[sqlite3.Row]:
        cur = self._conn.execute(
            "SELECT * FROM news_items WHERE arrived_at > ? ORDER BY arrived_at DESC",
            (iso_timestamp,),
        )
        return iter(cur.fetchall())
