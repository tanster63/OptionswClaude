"""Yahoo Finance adapters via yfinance."""

from __future__ import annotations

import datetime as dt

import yfinance as yf

from trading_assistant.ingest.market_data import Quote
from trading_assistant.ingest.options_chain import OptionContract


class YahooQuoteAdapter:
    def latest_quote(self, symbol: str) -> Quote:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        bid = float(getattr(info, "bid", 0.0) or 0.0)
        ask = float(getattr(info, "ask", 0.0) or 0.0)
        last = float(getattr(info, "last_price", 0.0) or 0.0)
        return Quote(
            symbol=symbol, bid=bid, ask=ask, last=last,
            ts=dt.datetime.now(dt.timezone.utc).isoformat(), source="yahoo",
        )


class YahooChainAdapter:
    def chain(self, symbol: str) -> list[OptionContract]:
        ticker = yf.Ticker(symbol)
        out: list[OptionContract] = []
        for expiry_str in ticker.options or []:
            expiry = dt.date.fromisoformat(expiry_str)
            chain = ticker.option_chain(expiry_str)
            for df, right in [(chain.calls, "C"), (chain.puts, "P")]:
                for row in df.itertuples():
                    out.append(OptionContract(
                        occ_symbol=str(getattr(row, "contractSymbol", "")),
                        underlying=symbol,
                        expiry=expiry,
                        strike=float(getattr(row, "strike", 0.0)),
                        right=right,  # type: ignore[arg-type]
                        bid=float(getattr(row, "bid", 0.0) or 0.0),
                        ask=float(getattr(row, "ask", 0.0) or 0.0),
                        last=float(getattr(row, "lastPrice", 0.0) or 0.0),
                        iv=float(getattr(row, "impliedVolatility", 0.0) or 0.0),
                    ))
        return out
