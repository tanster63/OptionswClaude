"""News signal generator — tags recent headlines with universe symbols."""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import sqlite3

from trading_assistant.signals.model import Signal, SignalKind

# Aliases: terms that imply exposure to specific underlyings.
# Conservative on purpose — false positives waste the LLM's attention.
_ALIASES: dict[str, frozenset[str]] = {
    "powell": frozenset({"SPY", "QQQ"}),
    "fomc": frozenset({"SPY", "QQQ"}),
    "fed funds": frozenset({"SPY", "QQQ"}),
    "russell 2000": frozenset({"IWM"}),
    "small cap": frozenset({"IWM"}),
    "dow jones": frozenset({"DIA"}),
    "nasdaq 100": frozenset({"QQQ"}),
    "s&p 500": frozenset({"SPY"}),
}


class NewsSignalGen:
    name = "news"

    def __init__(self, conn: sqlite3.Connection, universe: list[str], lookback_minutes: int = 60) -> None:
        self._conn = conn
        self._universe = [u.upper() for u in universe]
        self._lookback = dt.timedelta(minutes=lookback_minutes)

    def generate(self, now: dt.datetime) -> list[Signal]:
        cutoff = (now - self._lookback).isoformat()
        rows = self._conn.execute(
            """
            SELECT url_hash, source, title, snippet, published_at, arrived_at
            FROM news_items
            WHERE arrived_at >= ?
            ORDER BY arrived_at ASC
            """,
            (cutoff,),
        ).fetchall()

        out: list[Signal] = []
        for row in rows:
            title = row["title"]
            matched = self._match_symbols(title)
            for symbol in sorted(matched & set(self._universe)):
                sig_id = self._signal_id(row["url_hash"], symbol)
                out.append(
                    Signal(
                        id=sig_id,
                        kind=SignalKind.NEWS_CATALYST,
                        symbol=symbol,
                        created_at=now,
                        strength=0.5,
                        evidence={
                            "title": title,
                            "source": row["source"],
                            "published_at": row["published_at"],
                            "url_hash": row["url_hash"],
                        },
                    )
                )
        return out

    def _match_symbols(self, title: str) -> set[str]:
        matched: set[str] = set()
        lowered = title.lower()
        for sym in self._universe:
            if re.search(rf"\b{re.escape(sym)}\b", title):
                matched.add(sym)
        for term, syms in _ALIASES.items():
            if term in lowered:
                matched.update(syms)
        return matched

    @staticmethod
    def _signal_id(url_hash: str, symbol: str) -> str:
        h = hashlib.sha256(f"{url_hash}:{symbol}".encode()).hexdigest()
        return f"news_{h[:16]}"
