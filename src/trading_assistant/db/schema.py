"""Database schema and migration. Single-file DDL for simplicity in Phase 1."""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1

_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS app_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_locks (
    name        TEXT PRIMARY KEY,
    acquired_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    kind         TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_audit_log_kind_created
    ON audit_log(kind, created_at DESC);

CREATE TABLE IF NOT EXISTS signals (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    kind            TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    payload_json    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at DESC);

CREATE TABLE IF NOT EXISTS trade_intents (
    id                TEXT PRIMARY KEY,
    created_at        TEXT NOT NULL,
    signal_id         TEXT NOT NULL REFERENCES signals(id),
    symbol            TEXT NOT NULL,
    structure_json    TEXT NOT NULL,
    rationale_md      TEXT NOT NULL,
    user_thesis       TEXT,
    status            TEXT NOT NULL,
    rejection_reason  TEXT
);
CREATE INDEX IF NOT EXISTS idx_intents_created ON trade_intents(created_at DESC);

CREATE TABLE IF NOT EXISTS paper_orders (
    client_order_id   TEXT PRIMARY KEY,
    intent_id         TEXT NOT NULL REFERENCES trade_intents(id),
    submitted_at      TEXT NOT NULL,
    alpaca_order_id   TEXT,
    status            TEXT NOT NULL,
    raw_response_json TEXT
);

CREATE TABLE IF NOT EXISTS fills (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    client_order_id          TEXT NOT NULL REFERENCES paper_orders(client_order_id),
    filled_at                TEXT NOT NULL,
    qty                      REAL NOT NULL,
    alpaca_fill_price        REAL NOT NULL,
    realistic_fill_price     REAL NOT NULL,
    nbbo_bid                 REAL NOT NULL,
    nbbo_ask                 REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS news_items (
    url_hash       TEXT PRIMARY KEY,
    source         TEXT NOT NULL,
    title          TEXT NOT NULL,
    snippet        TEXT,
    published_at   TEXT,
    arrived_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_news_arrived ON news_items(arrived_at DESC);

CREATE TABLE IF NOT EXISTS econ_observations (
    series_id    TEXT NOT NULL,
    observation_date TEXT NOT NULL,
    value        REAL,
    fetched_at   TEXT NOT NULL,
    PRIMARY KEY (series_id, observation_date)
);
"""

_SEED_APP_STATE = [
    ("kill_switch", "off"),
    ("mode", "paper"),
]


def create_schema(conn: sqlite3.Connection) -> None:
    """Create all tables (idempotent) and record schema version."""
    conn.executescript(_DDL)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version(version) VALUES (?)",
        (SCHEMA_VERSION,),
    )
    for key, value in _SEED_APP_STATE:
        conn.execute(
            "INSERT OR IGNORE INTO app_state(key, value) VALUES (?, ?)",
            (key, value),
        )


def current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    return int(row["v"]) if row and row["v"] is not None else 0
