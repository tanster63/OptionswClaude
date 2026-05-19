"""Bar dataclass and BarSource Protocol tests."""

from __future__ import annotations

import datetime as dt

import pytest

from trading_assistant.ingest.bars import Bar, BarSource


def test_bar_is_frozen_dataclass():
    b = Bar(
        symbol="SPY",
        ts=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
        open=738.0,
        high=740.0,
        low=735.0,
        close=739.0,
        volume=1_000_000.0,
    )
    with pytest.raises(Exception):
        b.close = 999.0  # frozen


def test_bar_source_is_protocol():
    class _Fake:
        def daily_bars(self, symbol: str, start: dt.date, end: dt.date) -> list[Bar]:
            return []

    fake: BarSource = _Fake()
    assert fake.daily_bars("SPY", dt.date(2026, 1, 1), dt.date(2026, 5, 11)) == []
