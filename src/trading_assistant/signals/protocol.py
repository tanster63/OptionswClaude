"""Structural contract every signal generator implements."""

from __future__ import annotations

import datetime as dt
from typing import Protocol

from trading_assistant.signals.model import Signal


class SignalGenerator(Protocol):
    name: str

    def generate(self, now: dt.datetime) -> list[Signal]:
        """Read whatever state it needs and return 0+ signals valid at ``now``.

        Implementations must be pure with respect to wall-clock time: they take
        ``now`` as input rather than reading the system clock. This makes them
        reproducible in tests and in the backtest replay engine (Phase 5).
        """
        ...
