"""Persistence for Signal rows."""

from __future__ import annotations

import datetime as dt
import json
import sqlite3

from trading_assistant.signals.model import Signal, SignalKind


class SignalRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def write(self, signal: Signal) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO signals(id, created_at, kind, symbol, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                signal.id,
                signal.created_at.isoformat(),
                signal.kind.value,
                signal.symbol,
                json.dumps({"strength": signal.strength, "evidence": signal.evidence}),
            ),
        )
        self._conn.commit()

    def list_since(self, cutoff: dt.datetime) -> list[Signal]:
        rows = self._conn.execute(
            """
            SELECT id, created_at, kind, symbol, payload_json
            FROM signals
            WHERE created_at >= ?
            ORDER BY created_at ASC
            """,
            (cutoff.isoformat(),),
        ).fetchall()
        out: list[Signal] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            out.append(
                Signal(
                    id=row["id"],
                    kind=SignalKind(row["kind"]),
                    symbol=row["symbol"],
                    created_at=dt.datetime.fromisoformat(row["created_at"]),
                    strength=payload["strength"],
                    evidence=payload["evidence"],
                )
            )
        return out
