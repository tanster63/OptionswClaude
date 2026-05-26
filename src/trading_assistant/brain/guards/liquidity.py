"""LiquidityGuard: reject intents whose legs have insufficient volume or open interest."""

from __future__ import annotations

from typing import Protocol

from trading_assistant.brain.validator import GuardOutcome, GuardResult
from trading_assistant.ingest.options_chain import OptionContract
from trading_assistant.intents.model import TradeIntent


class _ChainClient(Protocol):
    def chain(self, symbol: str) -> list[OptionContract]: ...


class LiquidityGuard:
    name = "liquidity"

    def __init__(self, chain_client: _ChainClient,
                 min_volume: int, min_open_interest: int) -> None:
        self._chain = chain_client
        self._min_vol = min_volume
        self._min_oi = min_open_interest

    def check(self, intent: TradeIntent) -> GuardResult:
        chain = self._chain.chain(intent.symbol)
        for leg in intent.legs:
            match = next((c for c in chain
                          if c.strike == leg.strike and c.expiry == leg.expiry
                          and c.right == leg.right), None)
            if match is None:
                return GuardResult(outcome=GuardOutcome.REJECT,
                                   reason="leg_quote_missing")
            if match.volume < self._min_vol:
                return GuardResult(outcome=GuardOutcome.REJECT,
                                   reason="volume_too_low")
            if match.open_interest < self._min_oi:
                return GuardResult(outcome=GuardOutcome.REJECT,
                                   reason="open_interest_too_low")
        return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)
