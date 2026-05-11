"""Market data client with Alpaca primary + Yahoo fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import structlog

log = structlog.get_logger(__name__)


class DataSourceFailure(Exception):
    """Both primary and fallback data sources failed."""


@dataclass(frozen=True)
class Quote:
    symbol: str
    bid: float
    ask: float
    last: float
    ts: str
    source: str


class _QuoteSource(Protocol):
    def latest_quote(self, symbol: str) -> Quote: ...


class MarketDataClient:
    def __init__(self, *, primary: _QuoteSource, fallback: _QuoteSource) -> None:
        self._primary = primary
        self._fallback = fallback

    def snapshot(self, symbols: list[str]) -> dict[str, Quote]:
        out: dict[str, Quote] = {}
        for sym in symbols:
            try:
                out[sym] = self._primary.latest_quote(sym)
                continue
            except Exception as exc:  # noqa: BLE001
                log.warning("primary_quote_failed", symbol=sym, error=str(exc))
            try:
                out[sym] = self._fallback.latest_quote(sym)
            except Exception as exc:  # noqa: BLE001
                log.error("fallback_quote_failed", symbol=sym, error=str(exc))
                raise DataSourceFailure(f"both sources failed for {sym}") from exc
        return out
