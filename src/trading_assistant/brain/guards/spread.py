"""SpreadGuard: reject intents where any leg has too-wide bid-ask spread."""

from __future__ import annotations

from typing import Protocol

from trading_assistant.brain.validator import GuardOutcome, GuardResult
from trading_assistant.ingest.options_chain import OptionContract
from trading_assistant.intents.model import TradeIntent


class _ChainClient(Protocol):
    def chain(self, symbol: str) -> list[OptionContract]: ...


class SpreadGuard:
    name = "spread"

    def __init__(self, chain_client: _ChainClient, max_pct: float) -> None:
        self._chain = chain_client
        self._max = max_pct

    def check(self, intent: TradeIntent) -> GuardResult:
        chain = self._chain.chain(intent.symbol)
        for leg in intent.legs:
            match = self._find(chain, leg.strike, leg.expiry, leg.right)
            if match is None or match.bid <= 0 or match.ask <= 0:
                return GuardResult(outcome=GuardOutcome.REJECT,
                                   reason="leg_quote_missing")
            mid = (match.bid + match.ask) / 2.0
            if mid <= 0:
                return GuardResult(outcome=GuardOutcome.REJECT,
                                   reason="leg_quote_missing")
            spread_pct = (match.ask - match.bid) / mid
            if spread_pct > self._max:
                return GuardResult(outcome=GuardOutcome.REJECT,
                                   reason="spread_too_wide")
        return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)

    @staticmethod
    def _find(chain: list[OptionContract], strike: float, expiry, right: str) -> OptionContract | None:
        for c in chain:
            if c.strike == strike and c.expiry == expiry and c.right == right:
                return c
        return None
