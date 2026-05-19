"""Volatility regime signal generator.

Reads the current options chain and classifies median ATM IV as low/normal/high.
ATM is approximated as the 5 strikes nearest to the underlying mid quote.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from statistics import median
from typing import Protocol

from trading_assistant.ingest.market_data import Quote
from trading_assistant.ingest.options_chain import OptionContract
from trading_assistant.signals.model import Signal, SignalKind

_LOW_IV = 0.15
_HIGH_IV = 0.25
_ATM_WINDOW = 5


class _ChainClient(Protocol):
    def chain(self, symbol: str) -> list[OptionContract]: ...


class _QuoteClient(Protocol):
    def snapshot(self, symbols: list[str]) -> dict[str, Quote]: ...


class VolatilitySignalGen:
    name = "volatility"

    def __init__(self, chain_client: _ChainClient, quote_client: _QuoteClient,
                 universe: list[str]) -> None:
        self._chain = chain_client
        self._quote = quote_client
        self._universe = [u.upper() for u in universe]

    def generate(self, now: dt.datetime) -> list[Signal]:
        out: list[Signal] = []
        quotes = self._quote.snapshot(self._universe)
        for symbol in self._universe:
            q = quotes.get(symbol)
            if q is None:
                continue
            mid = (q.bid + q.ask) / 2.0
            chain = self._chain.chain(symbol)
            if not chain:
                continue
            atm = sorted(chain, key=lambda c: abs(c.strike - mid))[:_ATM_WINDOW]
            ivs = [c.iv for c in atm if c.iv is not None and c.iv > 0]
            if not ivs:
                continue
            med = median(ivs)
            regime: str | None
            if med >= _HIGH_IV:
                regime = "high"
            elif med <= _LOW_IV:
                regime = "low"
            else:
                regime = None
            if regime is None:
                continue
            out.append(self._sig(symbol, regime, med, now))
        return out

    @staticmethod
    def _sig(symbol: str, regime: str, iv: float, now: dt.datetime) -> Signal:
        key = f"vol:{symbol}:{regime}:{now.date().isoformat()}"
        sid = "vol_" + hashlib.sha256(key.encode()).hexdigest()[:16]
        return Signal(
            id=sid,
            kind=SignalKind.VOLATILITY_REGIME,
            symbol=symbol,
            created_at=now,
            strength=0.5,
            evidence={"regime": regime, "median_atm_iv": iv},
        )
