import pytest

from trading_assistant.ingest.market_data import (
    DataSourceFailure,
    MarketDataClient,
    Quote,
)


class FakeAlpaca:
    def __init__(self, quotes: dict[str, Quote] | None = None, raise_exc: bool = False):
        self._quotes = quotes or {}
        self._raise = raise_exc

    def latest_quote(self, symbol: str) -> Quote:
        if self._raise:
            raise RuntimeError("alpaca down")
        if symbol not in self._quotes:
            raise KeyError(symbol)
        return self._quotes[symbol]


class FakeYahoo:
    def __init__(self, quotes: dict[str, Quote] | None = None, raise_exc: bool = False):
        self._quotes = quotes or {}
        self._raise = raise_exc

    def latest_quote(self, symbol: str) -> Quote:
        if self._raise:
            raise RuntimeError("yahoo down")
        if symbol not in self._quotes:
            raise KeyError(symbol)
        return self._quotes[symbol]


def quote(sym: str, bid: float, ask: float, last: float) -> Quote:
    return Quote(
        symbol=sym, bid=bid, ask=ask, last=last,
        ts="2026-04-27T14:30:00Z", source="test",
    )


def test_uses_primary_when_healthy():
    primary = FakeAlpaca({"SPY": quote("SPY", 470.0, 470.05, 470.02)})
    fallback = FakeYahoo()
    client = MarketDataClient(primary=primary, fallback=fallback)
    q = client.snapshot(["SPY"])["SPY"]
    assert q.bid == 470.0
    assert q.source == "test"


def test_falls_back_when_primary_raises():
    primary = FakeAlpaca(raise_exc=True)
    fallback = FakeYahoo({"SPY": quote("SPY", 470.0, 470.05, 470.02)})
    client = MarketDataClient(primary=primary, fallback=fallback)
    q = client.snapshot(["SPY"])["SPY"]
    assert q.symbol == "SPY"


def test_raises_when_both_sources_fail():
    primary = FakeAlpaca(raise_exc=True)
    fallback = FakeYahoo(raise_exc=True)
    client = MarketDataClient(primary=primary, fallback=fallback)
    with pytest.raises(DataSourceFailure):
        client.snapshot(["SPY"])


def test_snapshot_supports_multiple_symbols():
    primary = FakeAlpaca({
        "SPY": quote("SPY", 470, 470.05, 470.02),
        "QQQ": quote("QQQ", 380, 380.04, 380.01),
    })
    fallback = FakeYahoo()
    client = MarketDataClient(primary=primary, fallback=fallback)
    snap = client.snapshot(["SPY", "QQQ"])
    assert set(snap.keys()) == {"SPY", "QQQ"}
