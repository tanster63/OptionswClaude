"""Validator + guard chain tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.validator import (
    GuardOutcome,
    GuardResult,
    Validator,
)
from trading_assistant.intents.model import Leg, Strategy, TradeIntent


def _intent() -> TradeIntent:
    return TradeIntent(
        id="i1",
        created_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
        signal_ids=["sig"],
        symbol="SPY",
        strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=740.0,
                   expiry=dt.date(2026, 6, 19), qty=1)],
        rationale_md="x",
        max_loss_usd=200.0,
        max_gain_usd=None,
        confidence=0.5,
    )


class _Always:
    name = "always"

    def __init__(self, outcome: GuardResult) -> None:
        self._out = outcome
        self.called = False

    def check(self, intent: TradeIntent) -> GuardResult:
        self.called = True
        return self._out


def test_accepts_when_all_guards_pass():
    g1 = _Always(GuardResult(outcome=GuardOutcome.ACCEPT, reason=None))
    g2 = _Always(GuardResult(outcome=GuardOutcome.ACCEPT, reason=None))
    v = Validator(guards=[g1, g2])
    decision = v.validate(_intent())
    assert decision.outcome == GuardOutcome.ACCEPT
    assert decision.reason is None
    assert g1.called and g2.called


def test_short_circuits_on_first_reject():
    g1 = _Always(GuardResult(outcome=GuardOutcome.REJECT, reason="spread_too_wide"))
    g2 = _Always(GuardResult(outcome=GuardOutcome.ACCEPT, reason=None))
    v = Validator(guards=[g1, g2])
    decision = v.validate(_intent())
    assert decision.outcome == GuardOutcome.REJECT
    assert decision.reason == "spread_too_wide"
    assert g1.called
    assert not g2.called


def test_no_guards_means_accept():
    v = Validator(guards=[])
    decision = v.validate(_intent())
    assert decision.outcome == GuardOutcome.ACCEPT
