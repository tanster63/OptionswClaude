"""DTEGuard: reject intents whose legs expire outside the swing window."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.validator import GuardOutcome, GuardResult
from trading_assistant.intents.model import TradeIntent


class DTEGuard:
    name = "dte"

    def __init__(self, min_dte: int, max_dte: int, now: dt.datetime) -> None:
        self._min = min_dte
        self._max = max_dte
        self._today = now.date()

    def check(self, intent: TradeIntent) -> GuardResult:
        for leg in intent.legs:
            days = (leg.expiry - self._today).days
            if days < self._min:
                return GuardResult(outcome=GuardOutcome.REJECT,
                                   reason="dte_too_short")
            if days > self._max:
                return GuardResult(outcome=GuardOutcome.REJECT,
                                   reason="dte_too_long")
        return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)
