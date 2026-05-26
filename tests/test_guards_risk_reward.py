"""MinRiskRewardGuard tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.guards.risk_reward import MinRiskRewardGuard
from trading_assistant.brain.validator import GuardOutcome
from trading_assistant.intents.model import Leg, Strategy, TradeIntent


def _intent(max_loss: float, max_gain: float | None) -> TradeIntent:
    return TradeIntent(
        id="i", created_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
        signal_ids=["s"], symbol="SPY", strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=740.0,
                   expiry=dt.date(2026, 6, 19), qty=1)],
        rationale_md="x", max_loss_usd=max_loss, max_gain_usd=max_gain, confidence=0.5,
    )


def test_accepts_when_ratio_meets_minimum():
    guard = MinRiskRewardGuard(min_ratio=1.0)
    assert guard.check(_intent(max_loss=100.0, max_gain=150.0)).outcome == GuardOutcome.ACCEPT


def test_accepts_when_ratio_equals_minimum_exactly():
    guard = MinRiskRewardGuard(min_ratio=1.0)
    assert guard.check(_intent(max_loss=100.0, max_gain=100.0)).outcome == GuardOutcome.ACCEPT


def test_rejects_when_ratio_below_minimum():
    guard = MinRiskRewardGuard(min_ratio=1.0)
    res = guard.check(_intent(max_loss=178.0, max_gain=122.0))  # 0.69 R/R
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "risk_reward_too_low"


def test_accepts_when_max_gain_is_none_unlimited_upside():
    """LONG_CALL with no defined max gain (unlimited theoretical upside) must pass."""
    guard = MinRiskRewardGuard(min_ratio=2.0)
    assert guard.check(_intent(max_loss=500.0, max_gain=None)).outcome == GuardOutcome.ACCEPT


def test_accepts_when_max_loss_is_zero_degenerate_case():
    """Don't crash on zero/negative max_loss — let other guards catch the real problem."""
    guard = MinRiskRewardGuard(min_ratio=1.0)
    # max_loss=0 is allowed by the TradeIntent model (Field(ge=0))
    assert guard.check(_intent(max_loss=0.0, max_gain=100.0)).outcome == GuardOutcome.ACCEPT
