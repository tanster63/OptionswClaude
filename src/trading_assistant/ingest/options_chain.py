"""Options chain client with yfinance primary + Alpaca fallback."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal, Protocol

import structlog

log = structlog.get_logger(__name__)


class DataSourceFailure(Exception):
    """Both primary and fallback options-chain sources failed."""


@dataclass(frozen=True)
class OptionContract:
    occ_symbol: str
    underlying: str
    expiry: dt.date
    strike: float
    right: Literal["C", "P"]
    bid: float
    ask: float
    last: float
    iv: float | None = None
    volume: int = 0
    open_interest: int = 0


class _ChainSource(Protocol):
    def chain(self, symbol: str) -> list[OptionContract]: ...


class OptionsChainClient:
    def __init__(self, *, primary: _ChainSource, fallback: _ChainSource) -> None:
        self._primary = primary
        self._fallback = fallback

    def chain(self, symbol: str) -> list[OptionContract]:
        try:
            return self._primary.chain(symbol)
        except Exception as exc:  # noqa: BLE001
            log.warning("primary_chain_failed", symbol=symbol, error=str(exc))
        try:
            return self._fallback.chain(symbol)
        except Exception as exc:  # noqa: BLE001
            log.error("fallback_chain_failed", symbol=symbol, error=str(exc))
            raise DataSourceFailure(f"both chain sources failed for {symbol}") from exc
