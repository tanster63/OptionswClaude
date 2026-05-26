"""NYSE market calendar wrapper. Always reason in America/New_York, never naive UTC."""

from __future__ import annotations

import datetime as dt
from enum import Enum
from zoneinfo import ZoneInfo

import pandas as pd
import pandas_market_calendars as mcal


class SessionState(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    HALF_DAY_OPEN = "half_day_open"


class MarketCalendar:
    def __init__(self) -> None:
        self._cal = mcal.get_calendar("XNYS")
        self.tz = ZoneInfo("America/New_York")

    def _now_utc(self) -> dt.datetime:
        return dt.datetime.now(dt.timezone.utc)

    def is_open_now(self, now: dt.datetime | None = None) -> bool:
        when = now or self._now_utc()
        sched = self._cal.schedule(
            start_date=(when - dt.timedelta(days=1)).date(),
            end_date=(when + dt.timedelta(days=1)).date(),
        )
        if sched.empty:
            return False
        ts = pd.Timestamp(when).tz_convert("UTC") if when.tzinfo else pd.Timestamp(when, tz="UTC")
        return any((row.market_open <= ts <= row.market_close) for row in sched.itertuples())

    def next_open(self, after: dt.datetime | None = None) -> dt.datetime:
        when = after or self._now_utc()
        sched = self._cal.schedule(
            start_date=when.date(),
            end_date=(when + dt.timedelta(days=14)).date(),
        )
        for row in sched.itertuples():
            if row.market_open.to_pydatetime() > when:
                return row.market_open.to_pydatetime()
        raise RuntimeError("no upcoming session within 14 days")

    def session_bounds(self, day: dt.date) -> tuple[dt.datetime, dt.datetime]:
        sched = self._cal.schedule(start_date=day, end_date=day)
        if sched.empty:
            raise ValueError(f"no session on {day}")
        row = next(sched.itertuples())
        return row.market_open.to_pydatetime(), row.market_close.to_pydatetime()

    def is_half_day(self, day: dt.date) -> bool:
        sched = self._cal.schedule(start_date=day, end_date=day)
        if sched.empty:
            return False
        row = next(sched.itertuples())
        close_et = row.market_close.tz_convert(self.tz)
        return close_et.hour < 16

    def session_state(self, now: dt.datetime | None = None) -> SessionState:
        """Return the current US market session state.

        - OPEN: regular trading session is in progress.
        - HALF_DAY_OPEN: an early-close day is in progress (still open).
        - CLOSED: weekend, holiday, before open, or after close.
        """
        when = now or self._now_utc()
        if not self.is_open_now(when):
            return SessionState.CLOSED
        if self.is_half_day(when.date()):
            return SessionState.HALF_DAY_OPEN
        return SessionState.OPEN
