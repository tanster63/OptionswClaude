"""StaleQuoteGuard: reject if the underlying quote is older than the freshness threshold."""

from __future__ import annotations

import datetime as dt
from typing import Protocol

from trading_assistant.brain.validator import GuardOutcome, GuardResult
from trading_assistant.ingest.market_data import Quote
from trading_assistant.intents.model import TradeIntent


class _QuoteClient(Protocol):
    def snapshot(self, symbols: list[str]) -> dict[str, Quote]: ...


class StaleQuoteGuard:
    name = "stale_quote"

    def __init__(self, quote_client: _QuoteClient, max_age_seconds: int,
                 now: dt.datetime) -> None:
        self._quote = quote_client
        self._max_age = max_age_seconds
        self._now = now

    def check(self, intent: TradeIntent) -> GuardResult:
        quotes = self._quote.snapshot([intent.symbol])
        q = quotes.get(intent.symbol)
        if q is None:
            return GuardResult(outcome=GuardOutcome.REJECT,
                               reason="underlying_quote_missing")
        try:
            ts = dt.datetime.fromisoformat(q.ts)
        except (ValueError, TypeError):
            return GuardResult(outcome=GuardOutcome.REJECT,
                               reason="underlying_quote_unparseable_ts")
        # Ensure both sides are timezone-aware UTC for safe arithmetic.
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=dt.timezone.utc)
        now_utc = self._now if self._now.tzinfo else self._now.replace(tzinfo=dt.timezone.utc)
        age_seconds = (now_utc - ts).total_seconds()
        if age_seconds > self._max_age:
            return GuardResult(outcome=GuardOutcome.REJECT,
                               reason="stale_underlying_quote")
        return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)
