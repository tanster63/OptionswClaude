"""News ingestion: RSS feeds (free) and Finnhub (free tier)."""

from __future__ import annotations

import datetime as dt
import hashlib
import sqlite3
from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.parse import urlparse

import httpx
import structlog

from trading_assistant.db.repositories import NewsRepo

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class NewsItem:
    url: str
    title: str
    snippet: str | None
    source: str
    published_at: str | None
    arrived_at: str

    @property
    def url_hash(self) -> str:
        return hashlib.sha256(self.url.encode("utf-8")).hexdigest()


class _NewsGateway(Protocol):
    def fetch(self) -> list[NewsItem]: ...


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class RSSGateway:
    """Pulls a list of RSS feeds. Parser is injected for testability.

    In production, pass `feedparser.parse` as the parser argument.
    """

    def __init__(self, *, parser: Callable[[str], object], urls: list[str]) -> None:
        self._parser = parser
        self._urls = urls

    def fetch(self) -> list[NewsItem]:
        items: list[NewsItem] = []
        for url in self._urls:
            try:
                parsed = self._parser(url)
            except Exception as exc:  # noqa: BLE001
                log.warning("rss_parse_failed", url=url, error=str(exc))
                continue
            host = urlparse(url).hostname or "unknown"
            for entry in getattr(parsed, "entries", []):
                items.append(NewsItem(
                    url=getattr(entry, "link", ""),
                    title=getattr(entry, "title", ""),
                    snippet=getattr(entry, "summary", None),
                    source=f"rss:{host}",
                    published_at=getattr(entry, "published", None),
                    arrived_at=_now_iso(),
                ))
        return items


class FinnhubGateway:
    def __init__(self, *, api_key: str, client: httpx.Client) -> None:
        self._api_key = api_key
        self._client = client

    def fetch_general(self) -> list[NewsItem]:
        resp = self._client.get(
            "https://finnhub.io/api/v1/news",
            params={"category": "general", "token": self._api_key},
            timeout=10.0,
        )
        resp.raise_for_status()
        out: list[NewsItem] = []
        for row in resp.json():
            out.append(NewsItem(
                url=row.get("url", ""),
                title=row.get("headline", ""),
                snippet=row.get("summary"),
                source="finnhub",
                published_at=dt.datetime.fromtimestamp(
                    row.get("datetime", 0), tz=dt.timezone.utc,
                ).isoformat() if row.get("datetime") else None,
                arrived_at=_now_iso(),
            ))
        return out

    def fetch(self) -> list[NewsItem]:
        return self.fetch_general()


class NewsClient:
    def __init__(self, *, gateways: list[_NewsGateway], conn: sqlite3.Connection) -> None:
        self._gateways = gateways
        self._repo = NewsRepo(conn)

    def refresh(self) -> int:
        """Fetch from all gateways, dedupe via url_hash, return count of new rows."""
        before = self._row_count()
        for gw in self._gateways:
            try:
                items = gw.fetch()
            except Exception as exc:  # noqa: BLE001
                log.warning("news_gateway_failed", gateway=type(gw).__name__, error=str(exc))
                continue
            for item in items:
                if not item.url:
                    continue
                self._repo.upsert(
                    url_hash=item.url_hash,
                    source=item.source,
                    title=item.title,
                    snippet=item.snippet,
                    published_at=item.published_at,
                    arrived_at=item.arrived_at,
                )
        return self._row_count() - before

    def _row_count(self) -> int:
        return self._repo._conn.execute(  # noqa: SLF001
            "SELECT COUNT(*) AS n FROM news_items"
        ).fetchone()["n"]
