"""StaleQuoteGuard tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.guards.stale_quote import StaleQuoteGuard
from trading_assistant.brain.validator import GuardOutcome
from trading_assistant.ingest.market_data import Quote
from trading_assistant.intents.model import Leg, Strategy, TradeIntent


_NOW = dt.datetime(2026, 5, 26, 14, 0, tzinfo=dt.timezone.utc)


class _FakeQuotes:
    def __init__(self, quotes: dict[str, Quote]) -> None:
        self._q = quotes

    def snapshot(self, symbols: list[str]) -> dict[str, Quote]:
        return {s: self._q[s] for s in symbols if s in self._q}


def _intent() -> TradeIntent:
    return TradeIntent(
        id="i", created_at=_NOW, signal_ids=["s"], symbol="SPY",
        strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=740.0,
                   expiry=dt.date(2026, 6, 19), qty=1)],
        rationale_md="x", max_loss_usd=100.0, max_gain_usd=None, confidence=0.5,
    )


def _quote(ts: dt.datetime) -> Quote:
    return Quote(symbol="SPY", bid=739.95, ask=740.05, last=740.00,
                 ts=ts.isoformat(), source="fake")


def test_accepts_fresh_quote():
    fresh = _NOW - dt.timedelta(seconds=60)
    guard = StaleQuoteGuard(quote_client=_FakeQuotes({"SPY": _quote(fresh)}),
                              max_age_seconds=900, now=_NOW)
    assert guard.check(_intent()).outcome == GuardOutcome.ACCEPT


def test_rejects_stale_quote():
    old = _NOW - dt.timedelta(seconds=1800)  # 30 min ago
    guard = StaleQuoteGuard(quote_client=_FakeQuotes({"SPY": _quote(old)}),
                              max_age_seconds=900, now=_NOW)
    res = guard.check(_intent())
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "stale_underlying_quote"


def test_rejects_when_quote_missing():
    guard = StaleQuoteGuard(quote_client=_FakeQuotes({}),
                              max_age_seconds=900, now=_NOW)
    res = guard.check(_intent())
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "underlying_quote_missing"


def test_rejects_unparseable_timestamp():
    bad_quote = Quote(symbol="SPY", bid=739.95, ask=740.05, last=740.00,
                       ts="not a real timestamp", source="fake")
    guard = StaleQuoteGuard(quote_client=_FakeQuotes({"SPY": bad_quote}),
                              max_age_seconds=900, now=_NOW)
    res = guard.check(_intent())
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "underlying_quote_unparseable_ts"


def test_skip_when_closed_returns_accept_regardless_of_quote_age():
    """When the orchestrator says market is closed, the guard short-circuits to ACCEPT."""
    very_old = _NOW - dt.timedelta(hours=72)
    guard = StaleQuoteGuard(
        quote_client=_FakeQuotes({"SPY": _quote(very_old)}),
        max_age_seconds=900, now=_NOW, skip_when_closed=True,
    )
    assert guard.check(_intent()).outcome == GuardOutcome.ACCEPT


def test_skip_when_closed_false_is_default_behavior():
    """Without skip_when_closed, stale quotes still reject (regression check)."""
    old = _NOW - dt.timedelta(seconds=1800)
    guard = StaleQuoteGuard(
        quote_client=_FakeQuotes({"SPY": _quote(old)}),
        max_age_seconds=900, now=_NOW,
    )
    res = guard.check(_intent())
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "stale_underlying_quote"
