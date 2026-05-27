"""PayoffMathGuard: verify intent's stated max_loss/max_gain against chain-derived math.

Catches LLM hallucinations in structured-output arithmetic (e.g., Claude stating
max_gain=188 when actual is 88 on a 750/752 bull call spread). Without this,
MinRiskRewardGuard operates on fabricated numbers.
"""

from __future__ import annotations

from typing import Protocol

from trading_assistant.brain.validator import GuardOutcome, GuardResult
from trading_assistant.ingest.options_chain import OptionContract
from trading_assistant.intents.model import Strategy, TradeIntent


class _ChainClient(Protocol):
    def chain(self, symbol: str) -> list[OptionContract]: ...


class PayoffMathGuard:
    name = "payoff_math"

    def __init__(self, chain_client: _ChainClient,
                 tolerance_pct: float = 0.05,
                 tolerance_min_usd: float = 20.0) -> None:
        self._chain = chain_client
        self._tol_pct = tolerance_pct
        self._tol_min = tolerance_min_usd

    def check(self, intent: TradeIntent) -> GuardResult:
        chain = self._chain.chain(intent.symbol)
        contracts: list[OptionContract] = []
        for leg in intent.legs:
            match = next((c for c in chain
                          if c.strike == leg.strike and c.expiry == leg.expiry
                          and c.right == leg.right), None)
            if match is None or match.bid <= 0 or match.ask <= 0:
                return GuardResult(outcome=GuardOutcome.REJECT,
                                   reason="leg_quote_missing")
            contracts.append(match)

        try:
            computed_loss, computed_gain = self._compute_payoff(intent, contracts)
        except _UnsupportedShape as exc:
            return GuardResult(outcome=GuardOutcome.REJECT, reason=str(exc))

        if not self._within_tolerance(computed_loss, intent.max_loss_usd):
            return GuardResult(outcome=GuardOutcome.REJECT,
                               reason="pnl_math_incorrect_max_loss")
        if computed_gain is not None and intent.max_gain_usd is not None:
            if not self._within_tolerance(computed_gain, intent.max_gain_usd):
                return GuardResult(outcome=GuardOutcome.REJECT,
                                   reason="pnl_math_incorrect_max_gain")

        return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)

    def _within_tolerance(self, computed: float, stated: float) -> bool:
        delta = abs(computed - stated)
        return delta <= max(self._tol_min, self._tol_pct * abs(computed))

    @staticmethod
    def _compute_payoff(intent: TradeIntent, contracts: list[OptionContract]
                         ) -> tuple[float, float | None]:
        """Return (max_loss_usd, max_gain_usd_or_None) computed from chain prices."""
        legs = intent.legs
        if intent.strategy == Strategy.LONG_CALL:
            # legs[0] is buy-call (enforced by TradeIntent.model_validator)
            premium = contracts[0].ask * 100.0 * legs[0].qty
            return premium, None  # unlimited upside

        if intent.strategy == Strategy.LONG_PUT:
            premium = contracts[0].ask * 100.0 * legs[0].qty
            # Max gain is stock-to-zero: strike value minus premium paid
            max_gain = (legs[0].strike * 100.0 * legs[0].qty) - premium
            return premium, max_gain

        if intent.strategy == Strategy.BULL_CALL_SPREAD:
            long_leg, long_c = _pair(legs, contracts, side="buy")
            short_leg, short_c = _pair(legs, contracts, side="sell")
            if long_leg.qty != short_leg.qty:
                raise _UnsupportedShape("unsupported_leg_qty_mismatch")
            qty = long_leg.qty
            net_debit = (long_c.ask - short_c.bid) * 100.0 * qty
            strike_width = (short_leg.strike - long_leg.strike) * 100.0 * qty
            max_loss = net_debit
            max_gain = strike_width - net_debit
            return max_loss, max_gain

        if intent.strategy == Strategy.BEAR_PUT_SPREAD:
            long_leg, long_c = _pair(legs, contracts, side="buy")
            short_leg, short_c = _pair(legs, contracts, side="sell")
            if long_leg.qty != short_leg.qty:
                raise _UnsupportedShape("unsupported_leg_qty_mismatch")
            qty = long_leg.qty
            net_debit = (long_c.ask - short_c.bid) * 100.0 * qty
            strike_width = (long_leg.strike - short_leg.strike) * 100.0 * qty
            max_loss = net_debit
            max_gain = strike_width - net_debit
            return max_loss, max_gain

        raise _UnsupportedShape("unsupported_strategy")


class _UnsupportedShape(Exception):
    """Raised when leg/strategy combination can't be priced by this guard."""


def _pair(legs, contracts, side: str):
    """Return (leg, contract) for the leg matching ``side``."""
    for leg, contract in zip(legs, contracts, strict=True):
        if leg.side == side:
            return leg, contract
    raise _UnsupportedShape(f"missing_{side}_leg")
