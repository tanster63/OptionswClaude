import datetime as dt

import pytest

from trading_assistant.ingest.options_chain import (
    DataSourceFailure,
    OptionContract,
    OptionsChainClient,
)


def contract(occ: str, bid: float, ask: float) -> OptionContract:
    return OptionContract(
        occ_symbol=occ,
        underlying="SPY",
        expiry=dt.date(2026, 5, 15),
        strike=470.0,
        right="C",
        bid=bid,
        ask=ask,
        last=(bid + ask) / 2,
        iv=0.18,
    )


class FakeYahoo:
    def __init__(self, chains=None, raise_exc=False):
        self._chains = chains or {}
        self._raise = raise_exc

    def chain(self, symbol: str) -> list[OptionContract]:
        if self._raise:
            raise RuntimeError("yahoo down")
        return self._chains.get(symbol, [])


class FakeAlpaca:
    def __init__(self, chains=None, raise_exc=False):
        self._chains = chains or {}
        self._raise = raise_exc

    def chain(self, symbol: str) -> list[OptionContract]:
        if self._raise:
            raise RuntimeError("alpaca down")
        return self._chains.get(symbol, [])


def test_returns_chain_from_primary():
    primary = FakeYahoo({"SPY": [contract("SPY...", 1.0, 1.1)]})
    fallback = FakeAlpaca()
    client = OptionsChainClient(primary=primary, fallback=fallback)
    chain = client.chain("SPY")
    assert len(chain) == 1
    assert chain[0].underlying == "SPY"


def test_falls_back_when_primary_raises():
    primary = FakeYahoo(raise_exc=True)
    fallback = FakeAlpaca({"SPY": [contract("SPY...", 1.0, 1.1)]})
    client = OptionsChainClient(primary=primary, fallback=fallback)
    chain = client.chain("SPY")
    assert len(chain) == 1


def test_raises_when_both_sources_fail():
    primary = FakeYahoo(raise_exc=True)
    fallback = FakeAlpaca(raise_exc=True)
    client = OptionsChainClient(primary=primary, fallback=fallback)
    with pytest.raises(DataSourceFailure):
        client.chain("SPY")


def test_returns_empty_chain_without_falling_back():
    """An empty chain is a *valid* answer, not a failure."""
    primary = FakeYahoo({"SPY": []})
    fallback = FakeAlpaca({"SPY": [contract("SPY...", 1.0, 1.1)]})
    client = OptionsChainClient(primary=primary, fallback=fallback)
    chain = client.chain("SPY")
    assert chain == []
