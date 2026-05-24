"""Alpaca SDK adapters for quote and chain protocols."""

from __future__ import annotations

import datetime as dt

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

from trading_assistant.ingest.bars import Bar
from trading_assistant.ingest.market_data import Quote
from trading_assistant.ingest.options_chain import OptionContract


class AlpacaQuoteAdapter:
    def __init__(self, *, api_key: str, secret_key: str) -> None:
        self._client = StockHistoricalDataClient(api_key=api_key, secret_key=secret_key)

    def latest_quote(self, symbol: str) -> Quote:
        req = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
        resp = self._client.get_stock_latest_quote(req)
        q = resp[symbol]
        return Quote(
            symbol=symbol,
            bid=float(q.bid_price or 0.0),
            ask=float(q.ask_price or 0.0),
            last=(float(q.bid_price or 0.0) + float(q.ask_price or 0.0)) / 2,
            ts=q.timestamp.isoformat() if q.timestamp else dt.datetime.now(dt.timezone.utc).isoformat(),
            source="alpaca",
        )


class AlpacaChainAdapter:
    """Stub: returns empty list. Real implementation depends on the user's
    Alpaca options data tier — wire this up once that's verified."""

    def __init__(self, *, api_key: str, secret_key: str) -> None:
        self._api_key = api_key
        self._secret_key = secret_key

    def chain(self, symbol: str) -> list[OptionContract]:
        return []


class AlpacaBarsAdapter:
    """Daily bars via Alpaca's historical data client."""

    def __init__(self, api_key: str, secret_key: str) -> None:
        from alpaca.data.historical import StockHistoricalDataClient

        self._client = StockHistoricalDataClient(api_key, secret_key)

    def daily_bars(self, symbol: str, start: dt.date, end: dt.date) -> list[Bar]:
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=dt.datetime.combine(start, dt.time.min, tzinfo=dt.timezone.utc),
            end=dt.datetime.combine(end, dt.time.max, tzinfo=dt.timezone.utc),
            feed=DataFeed.IEX,
        )
        resp = self._client.get_stock_bars(req)
        rows = resp.data.get(symbol, []) if hasattr(resp, "data") else []
        return [
            Bar(
                symbol=symbol,
                ts=row.timestamp,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
            )
            for row in rows
        ]
