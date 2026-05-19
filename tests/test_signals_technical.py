"""TechnicalSignalGen tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.ingest.bars import Bar
from trading_assistant.signals.model import SignalKind
from trading_assistant.signals.technical import TechnicalSignalGen


class _FakeBars:
    def __init__(self, bars_by_symbol: dict[str, list[Bar]]) -> None:
        self._bars = bars_by_symbol

    def daily_bars(self, symbol: str, start: dt.date, end: dt.date) -> list[Bar]:
        return list(self._bars.get(symbol, []))


def _bar(day: int, close: float, symbol: str = "SPY") -> Bar:
    return Bar(
        symbol=symbol,
        ts=dt.datetime(2026, 4, day, tzinfo=dt.timezone.utc),
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=1_000_000.0,
    )


def _flat_bars(symbol: str, days: int, base: float) -> list[Bar]:
    return [_bar(d, base, symbol) for d in range(1, days + 1)]


def test_emits_breakout_when_close_exceeds_20d_high():
    bars = _flat_bars("SPY", 20, 700.0)
    bars.append(_bar(21, 720.0))  # breakout
    gen = TechnicalSignalGen(bar_source=_FakeBars({"SPY": bars}), universe=["SPY"])
    signals = gen.generate(dt.datetime(2026, 4, 21, tzinfo=dt.timezone.utc))
    kinds = [s.kind for s in signals]
    assert SignalKind.TECHNICAL_BREAKOUT in kinds
    breakout = next(s for s in signals if s.kind == SignalKind.TECHNICAL_BREAKOUT)
    assert breakout.symbol == "SPY"
    assert breakout.evidence["direction"] == "up"


def test_no_breakout_when_close_is_within_range():
    bars = _flat_bars("SPY", 20, 700.0)
    bars.append(_bar(21, 700.5))
    gen = TechnicalSignalGen(bar_source=_FakeBars({"SPY": bars}), universe=["SPY"])
    signals = gen.generate(dt.datetime(2026, 4, 21, tzinfo=dt.timezone.utc))
    assert all(s.kind != SignalKind.TECHNICAL_BREAKOUT for s in signals)


def test_returns_empty_when_too_few_bars():
    gen = TechnicalSignalGen(
        bar_source=_FakeBars({"SPY": _flat_bars("SPY", 5, 700.0)}),
        universe=["SPY"],
    )
    assert gen.generate(dt.datetime(2026, 4, 5, tzinfo=dt.timezone.utc)) == []


def test_handles_missing_symbol_gracefully():
    gen = TechnicalSignalGen(bar_source=_FakeBars({}), universe=["SPY"])
    assert gen.generate(dt.datetime(2026, 4, 21, tzinfo=dt.timezone.utc)) == []
