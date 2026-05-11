"""Event calendar for FOMC/CPI/NFP/earnings event-window guards.

Phase 1 stores events in memory. Phase 2 will populate from FRED release schedule
+ a static earnings calendar.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum


class EventKind(str, Enum):
    FOMC = "fomc"
    CPI = "cpi"
    NFP = "nfp"
    EARNINGS = "earnings"


@dataclass(frozen=True)
class EconomicEvent:
    kind: EventKind
    date: dt.date
    symbols: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not isinstance(self.symbols, frozenset):
            object.__setattr__(self, "symbols", frozenset(self.symbols))


@dataclass
class EventCalendar:
    events: list[EconomicEvent]

    def events_in_window(self, start: dt.date, days: int) -> list[EconomicEvent]:
        end = start + dt.timedelta(days=days)
        return [e for e in self.events if start <= e.date <= end]

    def symbol_in_event_window(self, symbol: str, start: dt.date, days: int) -> bool:
        for e in self.events_in_window(start, days):
            if symbol in e.symbols:
                return True
        return False
