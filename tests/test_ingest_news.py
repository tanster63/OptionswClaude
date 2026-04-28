import datetime as dt

import httpx
import pytest
import respx

from trading_assistant.db.schema import create_schema
from trading_assistant.ingest.news import (
    FinnhubGateway,
    NewsClient,
    NewsItem,
    RSSGateway,
)


@pytest.fixture
def conn(db_conn):
    create_schema(db_conn)
    return db_conn


class FakeFeedParser:
    """Stand-in for feedparser.parse — returns a structlike object."""

    class _Entry:
        def __init__(self, link: str, title: str, summary: str, published: str):
            self.link = link
            self.title = title
            self.summary = summary
            self.published = published

    def __init__(self, entries: list[_Entry]):
        self.entries = entries

    @classmethod
    def from_pairs(cls, pairs: list[tuple[str, str]]) -> "FakeFeedParser":
        return cls([cls._Entry(url, title, "snippet", "2026-04-26T13:00:00Z")
                    for url, title in pairs])


def test_rss_gateway_fetches_and_normalizes():
    fake = FakeFeedParser.from_pairs([("https://x.com/a", "headline A")])
    gw = RSSGateway(parser=lambda url: fake, urls=["https://feed.example/rss"])
    items = gw.fetch()
    assert len(items) == 1
    assert items[0].title == "headline A"
    assert items[0].source == "rss:feed.example"


@respx.mock
def test_finnhub_gateway_calls_correct_url():
    respx.get("https://finnhub.io/api/v1/news").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "url": "https://news.example/x",
                    "headline": "headline X",
                    "summary": "snippet X",
                    "datetime": 1714137600,
                }
            ],
        )
    )
    gw = FinnhubGateway(api_key="key", client=httpx.Client())
    items = gw.fetch_general()
    assert len(items) == 1
    assert items[0].title == "headline X"
    assert items[0].source == "finnhub"


def test_news_client_persists_dedup(conn):
    gw1 = type("G", (), {"fetch": lambda self: [
        NewsItem(url="https://e/a", title="A", snippet=None, source="rss",
                 published_at=None, arrived_at="2026-04-27T14:00:00Z"),
        NewsItem(url="https://e/a", title="A-dup", snippet=None, source="rss",
                 published_at=None, arrived_at="2026-04-27T14:00:00Z"),
    ]})()
    client = NewsClient(gateways=[gw1], conn=conn)
    client.refresh()
    client.refresh()  # second call also no-ops on dup
    rows = list(conn.execute("SELECT url_hash, title FROM news_items"))
    assert len(rows) == 1
    assert rows[0]["title"] == "A"


def test_news_client_continues_when_one_gateway_fails(conn):
    class Bad:
        def fetch(self):
            raise RuntimeError("boom")

    class Good:
        def fetch(self):
            return [NewsItem(url="https://e/x", title="X", snippet=None, source="rss",
                             published_at=None, arrived_at="2026-04-27T14:00:00Z")]

    client = NewsClient(gateways=[Bad(), Good()], conn=conn)
    client.refresh()
    rows = list(conn.execute("SELECT title FROM news_items"))
    assert {r["title"] for r in rows} == {"X"}
