"""Persistence for TradeIntent rows."""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from dataclasses import dataclass

from trading_assistant.intents.model import Leg, Strategy, TradeIntent


@dataclass(frozen=True)
class TradeIntentRow:
    intent: TradeIntent
    status: str
    rejection_reason: str | None


class TradeIntentRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def write(self, intent: TradeIntent, status: str, rejection_reason: str | None) -> None:
        # The signals table requires signal_id to exist; for multi-signal intents
        # we record the first signal_id and store the full list inside structure_json.
        primary_signal_id = intent.signal_ids[0]
        structure = {
            "strategy": intent.strategy.value,
            "legs": [leg.model_dump(mode="json") for leg in intent.legs],
            "max_loss_usd": intent.max_loss_usd,
            "max_gain_usd": intent.max_gain_usd,
            "confidence": intent.confidence,
            "signal_ids": intent.signal_ids,
        }
        self._conn.execute(
            """
            INSERT OR REPLACE INTO trade_intents
                (id, created_at, signal_id, symbol, structure_json, rationale_md,
                 user_thesis, status, rejection_reason)
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                intent.id,
                intent.created_at.isoformat(),
                primary_signal_id,
                intent.symbol,
                json.dumps(structure),
                intent.rationale_md,
                status,
                rejection_reason,
            ),
        )
        self._conn.commit()

    def list_since(self, cutoff: dt.datetime) -> list[TradeIntentRow]:
        rows = self._conn.execute(
            """
            SELECT id, created_at, signal_id, symbol, structure_json, rationale_md,
                   status, rejection_reason
            FROM trade_intents
            WHERE created_at >= ?
            ORDER BY created_at ASC
            """,
            (cutoff.isoformat(),),
        ).fetchall()
        out: list[TradeIntentRow] = []
        for r in rows:
            struct = json.loads(r["structure_json"])
            intent = TradeIntent(
                id=r["id"],
                created_at=dt.datetime.fromisoformat(r["created_at"]),
                signal_ids=struct["signal_ids"],
                symbol=r["symbol"],
                strategy=Strategy(struct["strategy"]),
                legs=[Leg(**leg) for leg in struct["legs"]],
                rationale_md=r["rationale_md"],
                max_loss_usd=struct["max_loss_usd"],
                max_gain_usd=struct["max_gain_usd"],
                confidence=struct["confidence"],
            )
            out.append(TradeIntentRow(intent=intent, status=r["status"],
                                       rejection_reason=r["rejection_reason"]))
        return out
