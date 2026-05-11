import datetime as dt

from trading_assistant.calendars.events import (
    EconomicEvent,
    EventCalendar,
    EventKind,
)


def test_event_calendar_returns_empty_when_no_events():
    cal = EventCalendar(events=[])
    assert cal.events_in_window(dt.date(2026, 5, 1), days=5) == []


def test_event_calendar_filters_by_window():
    e1 = EconomicEvent(kind=EventKind.CPI, date=dt.date(2026, 5, 13), symbols={"SPY", "QQQ"})
    e2 = EconomicEvent(kind=EventKind.NFP, date=dt.date(2026, 6, 5), symbols={"IWM"})
    cal = EventCalendar(events=[e1, e2])
    in_window = cal.events_in_window(dt.date(2026, 5, 1), days=14)
    assert in_window == [e1]


def test_symbol_in_event_window_true_for_cpi_on_spy():
    e = EconomicEvent(kind=EventKind.CPI, date=dt.date(2026, 5, 13), symbols={"SPY", "QQQ"})
    cal = EventCalendar(events=[e])
    assert cal.symbol_in_event_window("SPY", dt.date(2026, 5, 12), days=2) is True


def test_symbol_in_event_window_false_for_unrelated_symbol():
    e = EconomicEvent(kind=EventKind.CPI, date=dt.date(2026, 5, 13), symbols={"SPY", "QQQ"})
    cal = EventCalendar(events=[e])
    assert cal.symbol_in_event_window("IWM", dt.date(2026, 5, 12), days=2) is False


def test_symbol_in_event_window_false_outside_window():
    e = EconomicEvent(kind=EventKind.FOMC, date=dt.date(2026, 6, 17), symbols={"SPY"})
    cal = EventCalendar(events=[e])
    assert cal.symbol_in_event_window("SPY", dt.date(2026, 5, 1), days=7) is False
