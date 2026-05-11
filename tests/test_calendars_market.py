import datetime as dt

from freezegun import freeze_time

from trading_assistant.calendars.market import MarketCalendar


def test_is_open_during_regular_hours():
    cal = MarketCalendar()
    with freeze_time("2026-04-27 14:30:00", tz_offset=0):  # Mon 10:30 ET
        assert cal.is_open_now() is True


def test_is_closed_outside_hours():
    cal = MarketCalendar()
    with freeze_time("2026-04-27 22:00:00", tz_offset=0):  # Mon 18:00 ET
        assert cal.is_open_now() is False


def test_is_closed_on_weekends():
    cal = MarketCalendar()
    with freeze_time("2026-04-25 14:30:00", tz_offset=0):  # Saturday
        assert cal.is_open_now() is False


def test_next_open_returns_future_datetime():
    cal = MarketCalendar()
    with freeze_time("2026-04-25 14:30:00", tz_offset=0):  # Saturday
        nxt = cal.next_open()
        assert nxt > dt.datetime(2026, 4, 25, tzinfo=dt.timezone.utc)
        assert nxt.astimezone(cal.tz).weekday() == 0


def test_session_bounds_returns_open_close_in_et():
    cal = MarketCalendar()
    open_dt, close_dt = cal.session_bounds(dt.date(2026, 4, 27))
    assert open_dt.astimezone(cal.tz).hour == 9
    assert open_dt.astimezone(cal.tz).minute == 30
    assert close_dt.astimezone(cal.tz).hour == 16
    assert close_dt.astimezone(cal.tz).minute == 0


def test_is_half_day_for_known_holiday():
    cal = MarketCalendar()
    # Day after Thanksgiving 2026 is a half day
    assert cal.is_half_day(dt.date(2026, 11, 27)) is True
    # Random Tuesday is not
    assert cal.is_half_day(dt.date(2026, 4, 28)) is False
