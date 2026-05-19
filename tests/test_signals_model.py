"""Signal model tests."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from trading_assistant.signals.model import Signal, SignalKind


def test_signal_round_trip_through_json():
    s = Signal(
        id="abc123",
        kind=SignalKind.TECHNICAL_BREAKOUT,
        symbol="QQQ",
        created_at=dt.datetime(2026, 5, 11, 14, 30, tzinfo=dt.timezone.utc),
        strength=0.7,
        evidence={"close": 712.5, "20d_high": 711.0},
    )
    raw = s.model_dump_json()
    parsed = Signal.model_validate_json(raw)
    assert parsed == s


def test_signal_strength_must_be_between_zero_and_one():
    with pytest.raises(ValidationError):
        Signal(
            id="x",
            kind=SignalKind.TECHNICAL_BREAKOUT,
            symbol="QQQ",
            created_at=dt.datetime.now(dt.timezone.utc),
            strength=1.5,
            evidence={},
        )


def test_signal_symbol_uppercased():
    s = Signal(
        id="x",
        kind=SignalKind.TECHNICAL_BREAKOUT,
        symbol="spy",
        created_at=dt.datetime.now(dt.timezone.utc),
        strength=0.5,
        evidence={},
    )
    assert s.symbol == "SPY"


def test_signal_kind_values():
    assert SignalKind.NEWS_CATALYST.value == "news_catalyst"
    assert SignalKind.TECHNICAL_BREAKOUT.value == "technical_breakout"
    assert SignalKind.VOLATILITY_REGIME.value == "volatility_regime"
    assert SignalKind.EVENT_PROXIMITY.value == "event_proximity"
