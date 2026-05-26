"""MinRiskRewardGuard: reject intents with max_gain/max_loss below a configured minimum."""

from __future__ import annotations

from trading_assistant.brain.validator import GuardOutcome, GuardResult
from trading_assistant.intents.model import TradeIntent


class MinRiskRewardGuard:
    name = "min_risk_reward"

    def __init__(self, min_ratio: float) -> None:
        self._min = min_ratio

    def check(self, intent: TradeIntent) -> GuardResult:
        # Unlimited-upside intents (e.g., LONG_CALL with no defined max gain) pass.
        if intent.max_gain_usd is None:
            return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)
        # Zero or negative max_loss is degenerate; let SpreadGuard / model validators catch it.
        if intent.max_loss_usd <= 0:
            return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)
        ratio = intent.max_gain_usd / intent.max_loss_usd
        if ratio < self._min:
            return GuardResult(outcome=GuardOutcome.REJECT,
                               reason="risk_reward_too_low")
        return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)
