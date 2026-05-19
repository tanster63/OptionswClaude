"""Event-proximity signal generator: upcoming FOMC/CPI/NFP/earnings."""

from __future__ import annotations

import datetime as dt
import hashlib

from trading_assistant.calendars.events import EventCalendar
from trading_assistant.signals.model import Signal, SignalKind


class EventProximitySignalGen:
    name = "event_proximity"

    def __init__(self, calendar: EventCalendar, universe: list[str], window_days: int = 5) -> None:
        self._cal = calendar
        self._universe = [u.upper() for u in universe]
        self._window = window_days

    def generate(self, now: dt.datetime) -> list[Signal]:
        today = now.date()
        events = self._cal.events_in_window(today, self._window)
        universe_set = set(self._universe)
        out: list[Signal] = []
        for ev in events:
            days_until = (ev.date - today).days
            for symbol in sorted(ev.symbols & universe_set):
                key = f"evt:{symbol}:{ev.kind.value}:{ev.date.isoformat()}"
                sid = "evt_" + hashlib.sha256(key.encode()).hexdigest()[:16]
                out.append(
                    Signal(
                        id=sid,
                        kind=SignalKind.EVENT_PROXIMITY,
                        symbol=symbol,
                        created_at=now,
                        strength=0.6,
                        evidence={
                            "event_kind": ev.kind.value,
                            "event_date": ev.date.isoformat(),
                            "days_until": days_until,
                        },
                    )
                )
        return out
