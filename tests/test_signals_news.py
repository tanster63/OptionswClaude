"""NewsSignalGen tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.db.schema import create_schema
from trading_assistant.ingest.news import NewsItem
from trading_assistant.db.repositories import NewsRepo
from trading_assistant.signals.model import SignalKind
from trading_assistant.signals.news import NewsSignalGen


def _put_news(repo: NewsRepo, title: str, arrived_at: dt.datetime, source: str = "rss:test") -> None:
    item = NewsItem(
        url=f"http://example.com/{title}",
        source=source,
        title=title,
        snippet="",
        published_at=arrived_at.isoformat(),
        arrived_at=arrived_at.isoformat(),
    )
    repo.upsert(
        url_hash=item.url_hash,
        source=item.source,
        title=item.title,
        snippet=item.snippet or "",
        published_at=item.published_at,
        arrived_at=item.arrived_at,
    )


def test_emits_signal_when_universe_symbol_in_title(db_conn):
    create_schema(db_conn)
    news_repo = NewsRepo(db_conn)
    now = dt.datetime(2026, 5, 11, 14, 0, tzinfo=dt.timezone.utc)
    _put_news(news_repo, "SPY breaks out to new highs", now - dt.timedelta(minutes=10))
    gen = NewsSignalGen(
        conn=db_conn,
        universe=["SPY", "QQQ", "IWM", "DIA"],
        lookback_minutes=60,
    )
    signals = gen.generate(now)
    assert len(signals) == 1
    assert signals[0].kind == SignalKind.NEWS_CATALYST
    assert signals[0].symbol == "SPY"
    assert "title" in signals[0].evidence


def test_ignores_news_outside_lookback_window(db_conn):
    create_schema(db_conn)
    news_repo = NewsRepo(db_conn)
    now = dt.datetime(2026, 5, 11, 14, 0, tzinfo=dt.timezone.utc)
    _put_news(news_repo, "SPY hits resistance", now - dt.timedelta(hours=3))
    gen = NewsSignalGen(conn=db_conn, universe=["SPY"], lookback_minutes=60)
    assert gen.generate(now) == []


def test_ignores_news_about_symbols_outside_universe(db_conn):
    create_schema(db_conn)
    news_repo = NewsRepo(db_conn)
    now = dt.datetime(2026, 5, 11, 14, 0, tzinfo=dt.timezone.utc)
    _put_news(news_repo, "AAPL crushes earnings", now - dt.timedelta(minutes=5))
    gen = NewsSignalGen(conn=db_conn, universe=["SPY", "QQQ"], lookback_minutes=60)
    assert gen.generate(now) == []


def test_powell_alias_tags_spy_and_qqq(db_conn):
    create_schema(db_conn)
    news_repo = NewsRepo(db_conn)
    now = dt.datetime(2026, 5, 11, 14, 0, tzinfo=dt.timezone.utc)
    _put_news(news_repo, "Powell signals June rate cut likely", now - dt.timedelta(minutes=5))
    gen = NewsSignalGen(conn=db_conn, universe=["SPY", "QQQ", "IWM", "DIA"], lookback_minutes=60)
    symbols = {s.symbol for s in gen.generate(now)}
    assert symbols == {"SPY", "QQQ"}
