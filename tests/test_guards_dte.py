"""DTEGuard tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.guards.dte import DTEGuard
from trading_assistant.brain.validator import GuardOutcome
from trading_assistant.intents.model import Leg, Strategy, TradeIntent


_NOW = dt.datetime(2026, 5, 26, tzinfo=dt.timezone.utc)


def _intent(expiry: dt.date) -> TradeIntent:
    return TradeIntent(
        id="i", created_at=_NOW, signal_ids=["s"], symbol="SPY",
        strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=740.0, expiry=expiry, qty=1)],
        rationale_md="x", max_loss_usd=100.0, max_gain_usd=None, confidence=0.5,
    )


def test_accepts_expiry_in_window():
    guard = DTEGuard(min_dte=14, max_dte=45, now=_NOW)
    assert guard.check(_intent(expiry=dt.date(2026, 6, 19))).outcome == GuardOutcome.ACCEPT


def test_accepts_at_lower_bound():
    guard = DTEGuard(min_dte=14, max_dte=45, now=_NOW)
    # 14 days from 5/26 is 6/9
    assert guard.check(_intent(expiry=dt.date(2026, 6, 9))).outcome == GuardOutcome.ACCEPT


def test_rejects_too_short():
    guard = DTEGuard(min_dte=14, max_dte=45, now=_NOW)
    res = guard.check(_intent(expiry=dt.date(2026, 6, 5)))  # 10 days
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "dte_too_short"


def test_rejects_too_long():
    guard = DTEGuard(min_dte=14, max_dte=45, now=_NOW)
    res = guard.check(_intent(expiry=dt.date(2026, 9, 18)))  # 115 days
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "dte_too_long"


def test_rejects_already_expired():
    guard = DTEGuard(min_dte=14, max_dte=45, now=_NOW)
    res = guard.check(_intent(expiry=dt.date(2026, 5, 20)))  # 6 days ago
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "dte_too_short"
