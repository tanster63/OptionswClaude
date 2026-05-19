"""EventProximitySignalGen tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.calendars.events import EconomicEvent, EventCalendar, EventKind
from trading_assistant.signals.event_proximity import EventProximitySignalGen
from trading_assistant.signals.model import SignalKind


def test_emits_signal_when_event_within_window():
    cal = EventCalendar(events=[
        EconomicEvent(
            kind=EventKind.FOMC,
            date=dt.date(2026, 5, 14),
            symbols=frozenset({"SPY", "QQQ"}),
        ),
    ])
    gen = EventProximitySignalGen(
        calendar=cal,
        universe=["SPY", "QQQ", "IWM", "DIA"],
        window_days=5,
    )
    sigs = gen.generate(dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    symbols = {s.symbol for s in sigs}
    assert symbols == {"SPY", "QQQ"}
    spy_sig = next(s for s in sigs if s.symbol == "SPY")
    assert spy_sig.kind == SignalKind.EVENT_PROXIMITY
    assert spy_sig.evidence["event_kind"] == "fomc"
    assert spy_sig.evidence["days_until"] == 3


def test_no_signal_when_no_event_in_window():
    cal = EventCalendar(events=[
        EconomicEvent(
            kind=EventKind.FOMC,
            date=dt.date(2026, 6, 14),
            symbols=frozenset({"SPY"}),
        ),
    ])
    gen = EventProximitySignalGen(calendar=cal, universe=["SPY"], window_days=5)
    assert gen.generate(dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc)) == []


def test_no_signal_for_symbols_outside_universe():
    cal = EventCalendar(events=[
        EconomicEvent(
            kind=EventKind.EARNINGS,
            date=dt.date(2026, 5, 12),
            symbols=frozenset({"NVDA"}),
        ),
    ])
    gen = EventProximitySignalGen(calendar=cal, universe=["SPY"], window_days=5)
    assert gen.generate(dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc)) == []
