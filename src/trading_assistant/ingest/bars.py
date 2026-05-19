"""Historical OHLCV bar abstraction."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Bar:
    symbol: str
    ts: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class BarSource(Protocol):
    def daily_bars(self, symbol: str, start: dt.date, end: dt.date) -> list[Bar]:
        """Return daily OHLCV bars in chronological order, inclusive on both ends."""
        ...
