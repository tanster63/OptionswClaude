"""EventWindowGuard tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.guards.event_window import EventWindowGuard
from trading_assistant.brain.validator import GuardOutcome
from trading_assistant.calendars.events import EconomicEvent, EventCalendar, EventKind
from trading_assistant.intents.model import Leg, Strategy, TradeIntent


def _intent(expiry: dt.date, symbol: str = "SPY") -> TradeIntent:
    return TradeIntent(
        id="i", created_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
        signal_ids=["s"], symbol=symbol, strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=740.0, expiry=expiry, qty=1)],
        rationale_md="x", max_loss_usd=200.0, max_gain_usd=None, confidence=0.5,
    )


def test_rejects_when_expiry_straddles_fomc():
    cal = EventCalendar(events=[
        EconomicEvent(kind=EventKind.FOMC, date=dt.date(2026, 5, 14),
                      symbols=frozenset({"SPY", "QQQ"})),
    ])
    guard = EventWindowGuard(calendar=cal,
                              now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    res = guard.check(_intent(expiry=dt.date(2026, 5, 16)))
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "event_window"


def test_accepts_when_expiry_before_event():
    cal = EventCalendar(events=[
        EconomicEvent(kind=EventKind.FOMC, date=dt.date(2026, 5, 14),
                      symbols=frozenset({"SPY"})),
    ])
    guard = EventWindowGuard(calendar=cal,
                              now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    assert guard.check(_intent(expiry=dt.date(2026, 5, 13))).outcome == GuardOutcome.ACCEPT


def test_accepts_when_event_affects_different_symbol():
    cal = EventCalendar(events=[
        EconomicEvent(kind=EventKind.EARNINGS, date=dt.date(2026, 5, 14),
                      symbols=frozenset({"NVDA"})),
    ])
    guard = EventWindowGuard(calendar=cal,
                              now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    assert guard.check(_intent(expiry=dt.date(2026, 5, 16))).outcome == GuardOutcome.ACCEPT
