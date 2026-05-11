"""CLI entry points for the trading assistant."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import structlog
import typer

from trading_assistant.config import load_config
from trading_assistant.db.connection import open_connection
from trading_assistant.db.schema import create_schema
from trading_assistant.logging_setup import configure_logging
from trading_assistant.secrets import load_secrets

app = typer.Typer(help="Local options trading assistant")
log = structlog.get_logger(__name__)


@app.command()
def snapshot(
    config: Path = typer.Option(..., exists=True, dir_okay=False, help="Path to config.yaml"),
    env: Path = typer.Option(..., exists=True, dir_okay=False, help="Path to .env secrets file"),
    db: Path = typer.Option(Path("./data/app.db"), help="Path to SQLite database file"),
) -> None:
    """Run a single ingestion cycle: market data + news + econ data, then print a summary."""
    cfg = load_config(config)
    secrets = load_secrets(env)
    configure_logging(level=cfg.log_level, json_output=cfg.log_json)
    conn = open_connection(db)
    create_schema(conn)

    log.info("snapshot_start", universe=cfg.universe, mode=cfg.mode)

    import feedparser
    import httpx

    from trading_assistant.adapters.alpaca import AlpacaChainAdapter, AlpacaQuoteAdapter
    from trading_assistant.adapters.fred import FredAdapter
    from trading_assistant.adapters.yahoo import YahooChainAdapter, YahooQuoteAdapter
    from trading_assistant.ingest.economic import EconomicDataClient
    from trading_assistant.ingest.market_data import MarketDataClient
    from trading_assistant.ingest.news import FinnhubGateway, NewsClient, RSSGateway
    from trading_assistant.ingest.options_chain import OptionsChainClient

    md = MarketDataClient(
        primary=AlpacaQuoteAdapter(api_key=secrets.alpaca_api_key,
                                    secret_key=secrets.alpaca_secret_key),
        fallback=YahooQuoteAdapter(),
    )
    oc = OptionsChainClient(
        primary=YahooChainAdapter(),
        fallback=AlpacaChainAdapter(api_key=secrets.alpaca_api_key,
                                     secret_key=secrets.alpaca_secret_key),
    )
    ec = EconomicDataClient(
        gateway=FredAdapter(api_key=secrets.fred_api_key),
        conn=conn,
    )
    nc = NewsClient(
        gateways=[
            RSSGateway(parser=feedparser.parse, urls=[
                "https://www.cnbc.com/id/100003114/device/rss/rss.html",
                "https://feeds.marketwatch.com/marketwatch/topstories/",
                "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=8-K&dateb=&owner=include&count=40&output=atom",
            ]),
            FinnhubGateway(api_key=secrets.finnhub_api_key, client=httpx.Client()),
        ],
        conn=conn,
    )

    quotes = md.snapshot(cfg.universe)
    chains = {sym: oc.chain(sym) for sym in cfg.universe}
    ec.refresh()
    new_news = nc.refresh()

    typer.echo("\n=== Snapshot ===")
    typer.echo(f"Time:    {dt.datetime.now(dt.timezone.utc).isoformat()}")
    typer.echo(f"Mode:    {cfg.mode}")
    typer.echo("\nQuotes:")
    for sym, q in quotes.items():
        typer.echo(f"  {sym}: bid={q.bid:.2f}  ask={q.ask:.2f}  last={q.last:.2f}  src={q.source}")
    typer.echo("\nChains:")
    for sym, contracts in chains.items():
        typer.echo(f"  {sym}: {len(contracts)} contracts")
    typer.echo(f"\nNews: {new_news} new headlines this cycle")
    typer.echo("Econ data refreshed.")
