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


def test_session_state_returns_open_during_regular_session():
    """A weekday afternoon during regular session hours returns OPEN."""
    import datetime as dt
    from trading_assistant.calendars.market import MarketCalendar, SessionState

    cal = MarketCalendar()
    # Wed 2026-05-13 18:30 UTC = 14:30 ET (regular session)
    when = dt.datetime(2026, 5, 13, 18, 30, tzinfo=dt.timezone.utc)
    state = cal.session_state(when)
    assert state == SessionState.OPEN


def test_session_state_returns_closed_outside_session():
    """A weeknight at midnight ET returns CLOSED."""
    import datetime as dt
    from trading_assistant.calendars.market import MarketCalendar, SessionState

    cal = MarketCalendar()
    # Wed 2026-05-13 05:00 UTC = 01:00 ET
    when = dt.datetime(2026, 5, 13, 5, 0, tzinfo=dt.timezone.utc)
    assert cal.session_state(when) == SessionState.CLOSED


def test_session_state_returns_closed_on_weekend():
    """Saturday afternoon returns CLOSED."""
    import datetime as dt
    from trading_assistant.calendars.market import MarketCalendar, SessionState

    cal = MarketCalendar()
    # Sat 2026-05-16 18:00 UTC = 14:00 ET (markets closed weekends)
    when = dt.datetime(2026, 5, 16, 18, 0, tzinfo=dt.timezone.utc)
    assert cal.session_state(when) == SessionState.CLOSED


def test_session_state_returns_closed_on_us_holiday_memorial_day():
    """Memorial Day 2026 (Mon 5/25) is a market holiday."""
    import datetime as dt
    from trading_assistant.calendars.market import MarketCalendar, SessionState

    cal = MarketCalendar()
    # Mon 2026-05-25 18:00 UTC = 14:00 ET on Memorial Day
    when = dt.datetime(2026, 5, 25, 18, 0, tzinfo=dt.timezone.utc)
    assert cal.session_state(when) == SessionState.CLOSED
