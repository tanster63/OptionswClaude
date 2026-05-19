"""SignalRepo tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.db.schema import create_schema
from trading_assistant.signals.model import Signal, SignalKind
from trading_assistant.signals.repo import SignalRepo


def _make(symbol: str, created_at: dt.datetime, kind: SignalKind = SignalKind.NEWS_CATALYST) -> Signal:
    return Signal(
        id=f"{symbol}-{created_at.isoformat()}",
        kind=kind,
        symbol=symbol,
        created_at=created_at,
        strength=0.5,
        evidence={"note": "test"},
    )


def test_write_and_round_trip(db_conn):
    create_schema(db_conn)
    repo = SignalRepo(db_conn)
    now = dt.datetime(2026, 5, 11, 14, 0, tzinfo=dt.timezone.utc)
    s = _make("SPY", now)
    repo.write(s)
    fetched = repo.list_since(now - dt.timedelta(minutes=1))
    assert len(fetched) == 1
    assert fetched[0] == s


def test_list_since_respects_cutoff(db_conn):
    create_schema(db_conn)
    repo = SignalRepo(db_conn)
    old = dt.datetime(2026, 5, 11, 10, 0, tzinfo=dt.timezone.utc)
    new = dt.datetime(2026, 5, 11, 14, 0, tzinfo=dt.timezone.utc)
    repo.write(_make("SPY", old))
    repo.write(_make("QQQ", new))
    out = repo.list_since(dt.datetime(2026, 5, 11, 12, 0, tzinfo=dt.timezone.utc))
    assert [s.symbol for s in out] == ["QQQ"]


def test_write_is_idempotent_on_id(db_conn):
    create_schema(db_conn)
    repo = SignalRepo(db_conn)
    s = _make("SPY", dt.datetime(2026, 5, 11, 14, 0, tzinfo=dt.timezone.utc))
    repo.write(s)
    repo.write(s)  # second write is a no-op
    assert len(repo.list_since(s.created_at - dt.timedelta(minutes=1))) == 1
