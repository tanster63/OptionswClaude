"""PinRiskGuard: reject if a short leg expires within 7d AND underlying is near strike."""

from __future__ import annotations

import datetime as dt
from typing import Protocol

from trading_assistant.brain.validator import GuardOutcome, GuardResult
from trading_assistant.ingest.market_data import Quote
from trading_assistant.intents.model import TradeIntent

_PIN_WINDOW_DAYS = 7


class _QuoteClient(Protocol):
    def snapshot(self, symbols: list[str]) -> dict[str, Quote]: ...


class PinRiskGuard:
    name = "pin_risk"

    def __init__(self, quote_client: _QuoteClient, pin_pct: float, now: dt.datetime) -> None:
        self._quote = quote_client
        self._pin = pin_pct
        self._now = now

    def check(self, intent: TradeIntent) -> GuardResult:
        short_legs = [l for l in intent.legs if l.side == "sell"]
        if not short_legs:
            return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)

        # Only care about legs expiring within the pin window.
        today = self._now.date()
        in_window = [l for l in short_legs
                      if (l.expiry - today).days <= _PIN_WINDOW_DAYS]
        if not in_window:
            return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)

        quotes = self._quote.snapshot([intent.symbol])
        q = quotes.get(intent.symbol)
        if q is None:
            return GuardResult(outcome=GuardOutcome.REJECT, reason="underlying_quote_missing")
        mid = (q.bid + q.ask) / 2.0
        band = mid * self._pin
        for leg in in_window:
            if abs(mid - leg.strike) <= band:
                return GuardResult(outcome=GuardOutcome.REJECT, reason="pin_risk")
        return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)
