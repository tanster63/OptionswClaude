"""TradeIntent model tests."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from trading_assistant.intents.model import Leg, Strategy, TradeIntent


def _leg(strike: float, side: str = "buy", right: str = "C") -> Leg:
    return Leg(side=side, right=right, strike=strike, expiry=dt.date(2026, 6, 19), qty=1)


def test_long_call_must_have_exactly_one_buy_call_leg():
    intent = TradeIntent(
        id="i1",
        created_at=dt.datetime.now(dt.timezone.utc),
        signal_ids=["s1"],
        symbol="SPY",
        strategy=Strategy.LONG_CALL,
        legs=[_leg(740.0)],
        rationale_md="QQQ broke 20d high",
        max_loss_usd=250.0,
        max_gain_usd=None,
        confidence=0.6,
    )
    assert intent.strategy == Strategy.LONG_CALL


def test_bull_call_spread_must_have_two_legs_long_lower_short_higher():
    intent = TradeIntent(
        id="i2",
        created_at=dt.datetime.now(dt.timezone.utc),
        signal_ids=["s1"],
        symbol="SPY",
        strategy=Strategy.BULL_CALL_SPREAD,
        legs=[_leg(740.0, side="buy"), _leg(745.0, side="sell")],
        rationale_md="long-call-spread thesis",
        max_loss_usd=150.0,
        max_gain_usd=350.0,
        confidence=0.65,
    )
    assert len(intent.legs) == 2


def test_bull_call_spread_rejects_wrong_leg_order():
    with pytest.raises(ValidationError):
        TradeIntent(
            id="i3",
            created_at=dt.datetime.now(dt.timezone.utc),
            signal_ids=["s1"],
            symbol="SPY",
            strategy=Strategy.BULL_CALL_SPREAD,
            legs=[_leg(745.0, side="buy"), _leg(740.0, side="sell")],
            rationale_md="x",
            max_loss_usd=100.0,
            max_gain_usd=200.0,
            confidence=0.5,
        )


def test_confidence_must_be_zero_to_one():
    with pytest.raises(ValidationError):
        TradeIntent(
            id="i4",
            created_at=dt.datetime.now(dt.timezone.utc),
            signal_ids=["s1"],
            symbol="SPY",
            strategy=Strategy.LONG_CALL,
            legs=[_leg(740.0)],
            rationale_md="x",
            max_loss_usd=100.0,
            max_gain_usd=None,
            confidence=1.5,
        )
