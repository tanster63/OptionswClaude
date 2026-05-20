"""IdeaCapGuard + DailyLossCapGuard tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.guards.caps import DailyLossCapGuard, IdeaCapGuard
from trading_assistant.brain.validator import GuardOutcome
from trading_assistant.db.repositories import AppStateRepo
from trading_assistant.db.schema import create_schema
from trading_assistant.intents.model import Leg, Strategy, TradeIntent
from trading_assistant.intents.repo import TradeIntentRepo


def _intent(intent_id: str, now: dt.datetime) -> TradeIntent:
    return TradeIntent(
        id=intent_id, created_at=now,
        signal_ids=["s"], symbol="SPY", strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=740.0,
                   expiry=dt.date(2026, 6, 19), qty=1)],
        rationale_md="x", max_loss_usd=200.0, max_gain_usd=None, confidence=0.5,
    )


def test_idea_cap_accepts_when_under_cap(db_conn):
    create_schema(db_conn)
    repo = TradeIntentRepo(db_conn)
    now = dt.datetime(2026, 5, 11, 14, tzinfo=dt.timezone.utc)
    guard = IdeaCapGuard(intent_repo=repo, cap=2, now=now)
    assert guard.check(_intent("i1", now)).outcome == GuardOutcome.ACCEPT


def test_idea_cap_rejects_when_cap_reached(db_conn):
    create_schema(db_conn)
    # Seed two already-validated intents for today.
    from trading_assistant.signals.model import Signal, SignalKind
    from trading_assistant.signals.repo import SignalRepo
    sig_repo = SignalRepo(db_conn)
    sig_repo.write(Signal(id="s", kind=SignalKind.NEWS_CATALYST, symbol="SPY",
                          created_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
                          strength=0.5, evidence={}))
    repo = TradeIntentRepo(db_conn)
    now = dt.datetime(2026, 5, 11, 14, tzinfo=dt.timezone.utc)
    repo.write(_intent("i1", now), status="validated", rejection_reason=None)
    repo.write(_intent("i2", now), status="validated", rejection_reason=None)
    guard = IdeaCapGuard(intent_repo=repo, cap=2, now=now)
    new_intent = _intent("i3", now)
    res = guard.check(new_intent)
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "idea_cap_reached"


def test_idea_cap_ignores_rejected_intents(db_conn):
    create_schema(db_conn)
    from trading_assistant.signals.model import Signal, SignalKind
    from trading_assistant.signals.repo import SignalRepo
    SignalRepo(db_conn).write(Signal(id="s", kind=SignalKind.NEWS_CATALYST, symbol="SPY",
                                      created_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
                                      strength=0.5, evidence={}))
    repo = TradeIntentRepo(db_conn)
    now = dt.datetime(2026, 5, 11, 14, tzinfo=dt.timezone.utc)
    repo.write(_intent("i1", now), status="rejected", rejection_reason="spread_too_wide")
    repo.write(_intent("i2", now), status="rejected", rejection_reason="pin_risk")
    guard = IdeaCapGuard(intent_repo=repo, cap=2, now=now)
    assert guard.check(_intent("i3", now)).outcome == GuardOutcome.ACCEPT


def test_daily_loss_cap_accepts_when_under_threshold(db_conn):
    create_schema(db_conn)
    AppStateRepo(db_conn).set("daily_realized_pnl_usd", "-100.0")
    guard = DailyLossCapGuard(state_repo=AppStateRepo(db_conn), loss_cap_usd=500.0)
    now = dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc)
    assert guard.check(_intent("i", now)).outcome == GuardOutcome.ACCEPT


def test_daily_loss_cap_rejects_when_loss_exceeds_cap(db_conn):
    create_schema(db_conn)
    AppStateRepo(db_conn).set("daily_realized_pnl_usd", "-600.0")
    guard = DailyLossCapGuard(state_repo=AppStateRepo(db_conn), loss_cap_usd=500.0)
    now = dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc)
    res = guard.check(_intent("i", now))
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "daily_loss_cap_hit"


def test_daily_loss_cap_treats_missing_state_as_zero(db_conn):
    create_schema(db_conn)
    guard = DailyLossCapGuard(state_repo=AppStateRepo(db_conn), loss_cap_usd=500.0)
    now = dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc)
    assert guard.check(_intent("i", now)).outcome == GuardOutcome.ACCEPT
