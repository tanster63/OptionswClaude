"""TradeIntentRepo tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.db.schema import create_schema
from trading_assistant.intents.model import Leg, Strategy, TradeIntent
from trading_assistant.intents.repo import TradeIntentRepo
from trading_assistant.signals.model import Signal, SignalKind
from trading_assistant.signals.repo import SignalRepo


def _make_intent(intent_id: str, signal_id: str, status: str = "validated") -> TradeIntent:
    return TradeIntent(
        id=intent_id,
        created_at=dt.datetime(2026, 5, 11, 14, tzinfo=dt.timezone.utc),
        signal_ids=[signal_id],
        symbol="SPY",
        strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=740.0, expiry=dt.date(2026, 6, 19), qty=1)],
        rationale_md="test thesis",
        max_loss_usd=200.0,
        max_gain_usd=None,
        confidence=0.6,
    )


def _persist_signal(conn, sid: str) -> None:
    repo = SignalRepo(conn)
    repo.write(Signal(
        id=sid,
        kind=SignalKind.NEWS_CATALYST,
        symbol="SPY",
        created_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
        strength=0.5,
        evidence={},
    ))


def test_write_validated_intent_round_trip(db_conn):
    create_schema(db_conn)
    _persist_signal(db_conn, "sig1")
    repo = TradeIntentRepo(db_conn)
    intent = _make_intent("i1", "sig1")
    repo.write(intent, status="validated", rejection_reason=None)
    fetched = repo.list_since(intent.created_at - dt.timedelta(minutes=1))
    assert len(fetched) == 1
    row = fetched[0]
    assert row.intent == intent
    assert row.status == "validated"
    assert row.rejection_reason is None


def test_write_rejected_intent_records_reason(db_conn):
    create_schema(db_conn)
    _persist_signal(db_conn, "sig2")
    repo = TradeIntentRepo(db_conn)
    intent = _make_intent("i2", "sig2")
    repo.write(intent, status="rejected", rejection_reason="spread_too_wide")
    fetched = repo.list_since(intent.created_at - dt.timedelta(minutes=1))
    assert fetched[0].rejection_reason == "spread_too_wide"
