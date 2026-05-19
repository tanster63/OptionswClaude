"""VolatilitySignalGen tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.ingest.options_chain import OptionContract
from trading_assistant.signals.model import SignalKind
from trading_assistant.signals.volatility import VolatilitySignalGen


class _FakeChains:
    def __init__(self, by_symbol: dict[str, list[OptionContract]]) -> None:
        self._chains = by_symbol

    def chain(self, symbol: str) -> list[OptionContract]:
        return list(self._chains.get(symbol, []))


class _FakeQuotes:
    def __init__(self, mids: dict[str, float]) -> None:
        self._mids = mids

    def snapshot(self, symbols: list[str]) -> dict:
        from trading_assistant.ingest.market_data import Quote

        out = {}
        for s in symbols:
            m = self._mids.get(s)
            if m is None:
                continue
            out[s] = Quote(symbol=s, bid=m - 0.05, ask=m + 0.05, last=m,
                           ts=dt.datetime.now(dt.timezone.utc), source="fake")
        return out


def _opt(strike: float, iv: float, right: str = "C", days_to_exp: int = 30) -> OptionContract:
    return OptionContract(
        occ_symbol=f"X{strike}{right}",
        underlying="SPY",
        expiry=(dt.datetime(2026, 5, 11) + dt.timedelta(days=days_to_exp)).date(),
        strike=strike,
        right=right,
        bid=1.0,
        ask=1.1,
        last=1.05,
        iv=iv,
    )


def test_emits_high_iv_signal_when_median_atm_iv_above_threshold():
    chain = [_opt(700, 0.30), _opt(710, 0.32), _opt(720, 0.28)]
    gen = VolatilitySignalGen(
        chain_client=_FakeChains({"SPY": chain}),
        quote_client=_FakeQuotes({"SPY": 710.0}),
        universe=["SPY"],
    )
    signals = gen.generate(dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    assert len(signals) == 1
    assert signals[0].kind == SignalKind.VOLATILITY_REGIME
    assert signals[0].evidence["regime"] == "high"


def test_emits_low_iv_signal_when_median_atm_iv_below_threshold():
    chain = [_opt(700, 0.10), _opt(710, 0.12), _opt(720, 0.11)]
    gen = VolatilitySignalGen(
        chain_client=_FakeChains({"SPY": chain}),
        quote_client=_FakeQuotes({"SPY": 710.0}),
        universe=["SPY"],
    )
    signals = gen.generate(dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    assert len(signals) == 1
    assert signals[0].evidence["regime"] == "low"


def test_no_signal_in_normal_regime():
    chain = [_opt(700, 0.20), _opt(710, 0.18), _opt(720, 0.22)]
    gen = VolatilitySignalGen(
        chain_client=_FakeChains({"SPY": chain}),
        quote_client=_FakeQuotes({"SPY": 710.0}),
        universe=["SPY"],
    )
    assert gen.generate(dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc)) == []


def test_empty_chain_returns_no_signal():
    gen = VolatilitySignalGen(
        chain_client=_FakeChains({}),
        quote_client=_FakeQuotes({"SPY": 710.0}),
        universe=["SPY"],
    )
    assert gen.generate(dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc)) == []
