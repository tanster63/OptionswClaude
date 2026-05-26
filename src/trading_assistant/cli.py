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


def _wire_ingestion(cfg, secrets, conn):
    """Build the ingestion clients used by both snapshot and synthesize."""
    import feedparser
    import httpx

    from trading_assistant.adapters.alpaca import (
        AlpacaChainAdapter,
        AlpacaQuoteAdapter,
    )
    from trading_assistant.adapters.fred import FredAdapter
    from trading_assistant.adapters.yahoo import (
        YahooChainAdapter,
        YahooQuoteAdapter,
    )
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
            FinnhubGateway(api_key=secrets.finnhub_api_key,
                            client=httpx.Client(timeout=15.0)),
        ],
        conn=conn,
    )
    return md, oc, ec, nc


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
    md, oc, ec, nc = _wire_ingestion(cfg, secrets, conn)

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


@app.command()
def synthesize(
    config: Path = typer.Option(..., exists=True, dir_okay=False),
    env: Path = typer.Option(..., exists=True, dir_okay=False),
    db: Path = typer.Option(Path("./data/app.db")),
    llm_model: str = typer.Option("claude-opus-4-7", help="Anthropic model id"),
    max_tokens: int = typer.Option(2000, help="Hard cap on LLM output tokens"),
) -> None:
    """Run ingest -> signals -> LLM synthesize -> validate. Print accepted intents."""
    import anthropic

    from trading_assistant.brain.anthropic_client import AnthropicClient
    from trading_assistant.brain.guards.caps import DailyLossCapGuard, IdeaCapGuard
    from trading_assistant.brain.guards.dte import DTEGuard
    from trading_assistant.brain.guards.event_window import EventWindowGuard
    from trading_assistant.brain.guards.liquidity import LiquidityGuard
    from trading_assistant.brain.guards.pin_risk import PinRiskGuard
    from trading_assistant.brain.guards.risk_reward import MinRiskRewardGuard
    from trading_assistant.brain.guards.spread import SpreadGuard
    from trading_assistant.brain.guards.stale_quote import StaleQuoteGuard
    from trading_assistant.brain.synthesizer import IdeaSynthesizer
    from trading_assistant.brain.validator import GuardOutcome, Validator
    from trading_assistant.calendars.events import EventCalendar
    from trading_assistant.db.repositories import AppStateRepo
    from trading_assistant.intents.repo import TradeIntentRepo
    from trading_assistant.signals.event_proximity import EventProximitySignalGen
    from trading_assistant.signals.news import NewsSignalGen
    from trading_assistant.signals.repo import SignalRepo
    from trading_assistant.signals.technical import TechnicalSignalGen
    from trading_assistant.signals.volatility import VolatilitySignalGen

    cfg = load_config(config)
    secrets = load_secrets(env)
    configure_logging(level=cfg.log_level, json_output=cfg.log_json)
    conn = open_connection(db)
    create_schema(conn)

    now = dt.datetime.now(dt.timezone.utc)
    log.info("synthesize_start", universe=cfg.universe, now=now.isoformat())

    md, oc, ec, nc = _wire_ingestion(cfg, secrets, conn)
    quotes = md.snapshot(cfg.universe)
    ec.refresh()
    nc.refresh()

    from trading_assistant.adapters.alpaca import AlpacaBarsAdapter
    bars = AlpacaBarsAdapter(api_key=secrets.alpaca_api_key,
                              secret_key=secrets.alpaca_secret_key)

    # Empty event calendar for now; Phase 3 will seed it from a real source.
    event_cal = EventCalendar(events=[])

    sig_repo = SignalRepo(conn)
    gens = [
        NewsSignalGen(conn=conn, universe=cfg.universe, lookback_minutes=60),
        TechnicalSignalGen(bar_source=bars, universe=cfg.universe),
        VolatilitySignalGen(chain_client=oc, quote_client=md, universe=cfg.universe),
        EventProximitySignalGen(calendar=event_cal, universe=cfg.universe, window_days=5),
    ]
    all_signals = []
    for gen in gens:
        sigs = gen.generate(now)
        for s in sigs:
            sig_repo.write(s)
        all_signals.extend(sigs)
        log.info("signals_generated", generator=gen.name, count=len(sigs))

    sdk = anthropic.Anthropic(api_key=secrets.anthropic_api_key)
    llm = AnthropicClient(sdk=sdk, model=llm_model, max_tokens=max_tokens)
    synth = IdeaSynthesizer(llm=llm, universe=cfg.universe)

    recent_news_rows = conn.execute(
        "SELECT title, source, published_at FROM news_items "
        "WHERE arrived_at >= ? ORDER BY arrived_at DESC LIMIT 20",
        ((now - dt.timedelta(hours=4)).isoformat(),),
    ).fetchall()
    recent_news = [{"title": r["title"], "source": r["source"],
                     "published_at": r["published_at"]} for r in recent_news_rows]

    # Build a chain "menu" for Claude: for each symbol, the next 4 expiries
    # in the 14-45 day swing window, with ±5% ATM strikes per expiry.
    chain_menu: dict[str, list[dict]] = {}
    today = now.date()
    for sym in cfg.universe:
        q = quotes.get(sym)
        if q is None:
            continue
        mid = (q.bid + q.ask) / 2.0
        full_chain = oc.chain(sym)
        if not full_chain:
            continue
        valid = [c for c in full_chain
                 if 14 <= (c.expiry - today).days <= 45
                 and abs(c.strike - mid) <= mid * 0.05]
        # Trim per expiry to keep the prompt small.
        by_exp: dict = {}
        for c in valid:
            by_exp.setdefault(c.expiry, []).append(c)
        picked: list[dict] = []
        for expiry in sorted(by_exp.keys())[:4]:
            contracts = sorted(by_exp[expiry], key=lambda c: abs(c.strike - mid))[:12]
            for c in contracts:
                picked.append({"expiry": c.expiry.isoformat(), "strike": c.strike,
                               "right": c.right, "bid": c.bid, "ask": c.ask,
                               "volume": c.volume, "open_interest": c.open_interest})
        chain_menu[sym] = picked

    candidates = synth.synthesize(signals=all_signals, quotes=quotes,
                                   recent_news=recent_news, now=now,
                                   chain_menu=chain_menu)

    intent_repo = TradeIntentRepo(conn)
    validator = Validator(guards=[
        DTEGuard(min_dte=cfg.min_dte, max_dte=cfg.max_dte, now=now),
        SpreadGuard(chain_client=oc, max_pct=cfg.max_spread_pct_of_mid),
        LiquidityGuard(chain_client=oc,
                        min_volume=cfg.min_option_volume,
                        min_open_interest=cfg.min_option_open_interest),
        StaleQuoteGuard(quote_client=md,
                         max_age_seconds=cfg.quote_stale_seconds, now=now),
        PinRiskGuard(quote_client=md, pin_pct=cfg.pin_risk_pct, now=now),
        EventWindowGuard(calendar=event_cal, now=now),
        MinRiskRewardGuard(min_ratio=cfg.min_risk_reward_ratio),
        IdeaCapGuard(intent_repo=intent_repo, cap=cfg.daily_idea_cap, now=now),
        DailyLossCapGuard(state_repo=AppStateRepo(conn),
                           loss_cap_usd=cfg.daily_loss_cap_usd),
    ])

    accepted = []
    for intent in candidates:
        decision = validator.validate(intent)
        if decision.outcome == GuardOutcome.ACCEPT:
            intent_repo.write(intent, status="validated", rejection_reason=None)
            accepted.append(intent)
        else:
            intent_repo.write(intent, status="rejected", rejection_reason=decision.reason)

    typer.echo("\n=== Synthesis ===")
    typer.echo(f"Time:       {now.isoformat()}")
    typer.echo(f"Signals:    {len(all_signals)}")
    typer.echo(f"Candidates: {len(candidates)}")
    typer.echo(f"Accepted:   {len(accepted)}")
    typer.echo(f"Rejected:   {len(candidates) - len(accepted)}")

    for intent in accepted:
        typer.echo("\n---")
        typer.echo(f"{intent.symbol}  {intent.strategy.value}  confidence={intent.confidence:.2f}")
        for leg in intent.legs:
            typer.echo(f"  {leg.side:>4} {leg.qty}x {leg.right} @ {leg.strike:.2f} exp {leg.expiry}")
        typer.echo(f"Max loss: ${intent.max_loss_usd:.2f}")
        if intent.max_gain_usd is not None:
            typer.echo(f"Max gain: ${intent.max_gain_usd:.2f}")
        typer.echo(f"\nRationale:\n{intent.rationale_md}")


@app.command()
def check_holding(
    symbol: str = typer.Option(..., help="Ticker symbol, e.g. OUST"),
    shares: float = typer.Option(..., help="Shares owned (use 0 if 'considering buying')"),
    cost_basis: float = typer.Option(..., help="Price per share paid"),
    account: str = typer.Option("taxable",
                                 help="Account type: taxable | roth | ira | unknown"),
    config: Path = typer.Option(..., exists=True, dir_okay=False),
    env: Path = typer.Option(..., exists=True, dir_okay=False),
    db: Path = typer.Option(Path("./data/app.db")),
    llm_model: str = typer.Option("claude-opus-4-7"),
    max_tokens: int = typer.Option(1500),
) -> None:
    """Pull fresh data on a stock you own (or are considering) and get a HOLD/TRIM/SELL/BUY_MORE recommendation."""
    import statistics

    import anthropic

    from trading_assistant.adapters.alpaca import AlpacaBarsAdapter
    from trading_assistant.adapters.yahoo import YahooChainAdapter, YahooQuoteAdapter
    from trading_assistant.brain.anthropic_client import AnthropicClient
    from trading_assistant.brain.holding_analyst import HoldingAnalyst, HoldingContext

    cfg = load_config(config)
    secrets = load_secrets(env)
    configure_logging(level=cfg.log_level, json_output=cfg.log_json)
    conn = open_connection(db)
    create_schema(conn)

    symbol = symbol.upper()
    log.info("check_holding_start", symbol=symbol, shares=shares,
             cost_basis=cost_basis, account=account)

    # Quote (Yahoo - works for any ticker)
    q = YahooQuoteAdapter().latest_quote(symbol)

    # Bars (Alpaca IEX, 120 days)
    bars = AlpacaBarsAdapter(api_key=secrets.alpaca_api_key,
                              secret_key=secrets.alpaca_secret_key).daily_bars(
        symbol, dt.date.today() - dt.timedelta(days=120), dt.date.today()
    )

    # IV summary (optional; if no chain, just skip)
    iv_summary = None
    try:
        chain = YahooChainAdapter().chain(symbol)
        if chain:
            mid = (q.bid + q.ask) / 2 if q.bid > 0 and q.ask > 0 else q.last
            atm = sorted(chain, key=lambda c: abs(c.strike - mid))[:6]
            ivs = [c.iv for c in atm if c.iv is not None and c.iv > 0]
            if ivs:
                med = statistics.median(ivs)
                regime = "high" if med >= 0.25 else "low" if med <= 0.15 else "normal"
                iv_summary = {"median_atm_iv": med, "regime": regime}
    except Exception as exc:
        log.warning("chain_fetch_failed_for_holding", symbol=symbol, error=str(exc))

    # Recent news matching this symbol (last 7 days)
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)).isoformat()
    news_rows = conn.execute(
        "SELECT title, source, published_at FROM news_items "
        "WHERE arrived_at >= ? AND (title LIKE ? OR title LIKE ?) "
        "ORDER BY arrived_at DESC LIMIT 15",
        (cutoff, f"%{symbol}%", f"%{symbol.lower()}%"),
    ).fetchall()
    recent_news = [{"title": r["title"], "source": r["source"],
                     "published_at": r["published_at"]} for r in news_rows]

    ctx = HoldingContext(
        symbol=symbol, shares=shares, cost_basis=cost_basis, account=account,
        current_quote=q, bars_90d=bars, iv_summary=iv_summary, recent_news=recent_news,
    )

    sdk = anthropic.Anthropic(api_key=secrets.anthropic_api_key)
    llm = AnthropicClient(sdk=sdk, model=llm_model, max_tokens=max_tokens)
    analyst = HoldingAnalyst(llm=llm)
    rec = analyst.analyze(ctx)

    typer.echo(f"\n=== Holding Check: {symbol} ===")
    mid = (q.bid + q.ask) / 2 if q.bid > 0 and q.ask > 0 else q.last
    if shares > 0 and cost_basis > 0:
        pnl_pct = (mid / cost_basis - 1) * 100
        pnl_total = (mid - cost_basis) * shares
        typer.echo(f"Position:        {shares} shares @ cost ${cost_basis:.2f}  "
                   f"(current ${mid:.2f}, {pnl_pct:+.1f}%, ${pnl_total:+,.2f})")
    else:
        typer.echo(f"Position:        considering purchase (current ${mid:.2f})")
    typer.echo(f"Account:         {account}")

    if rec is None:
        typer.echo("\nAnalysis failed - LLM call errored or response unparseable. Check logs.")
        raise typer.Exit(code=1)

    typer.echo(f"\nRecommendation:  {rec.action.value.upper()}   confidence {rec.confidence:.2f}")
    typer.echo(f"\nReasoning:\n{rec.rationale_md}")
    if rec.key_risks:
        typer.echo("\nKey risks:")
        for r in rec.key_risks:
            typer.echo(f"  - {r}")
    if rec.tax_note:
        typer.echo(f"\nTax note: {rec.tax_note}")
    typer.echo("\n(This is analysis to consider, not investment advice.)")
