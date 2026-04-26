# Options Trading Assistant — Design Spec

**Date:** 2026-04-26
**Status:** Design approved, awaiting user spec review before writing implementation plan
**Owner:** Claude builds; user is sole end user (non-technical)

---

## 1. Goal and non-goals

### Goal

A local Mac application that helps a beginning options trader learn, paper-trade, and eventually become profitable on US-listed options. The system surfaces a small number of high-quality trade ideas per day with structured reasoning, lets the user approve and one-click-execute on a paper account, tracks outcomes, and pushes alerts to the user's phone.

### Non-goals (MVP)

- Live (real-money) trading
- Intraday day trading
- Universe larger than four ETFs
- Conversational chat interface
- Multi-user, accounts, auth, or cloud hosting
- Mobile native app
- Mac menu-bar icon or other "polish" features
- Pre-design for intraday (we will refactor when the time comes)

### Success criteria for MVP

1. The app installs and runs on the user's Mac with one command.
2. During market hours, it scans SPY/QQQ/IWM/DIA, ingests news + economic data, and surfaces at most **2 trade ideas per day**, each with structured reasoning and citations.
3. The user can review an idea, write a one-line thesis, then one-click execute as a paper trade via Alpaca.
4. The system journals every idea, every paper trade, every fill, and every outcome.
5. The user receives a Pushover phone alert for each new idea.
6. A weekly retrospective screen shows predicted-vs-realized performance broken down by Claude-generated ideas vs user-overrides.
7. A backtest/replay mode reproduces what ideas the system would have generated on historical data spanning at least one VIX>30 regime.

---

## 2. Staged plan (project context)

The MVP is **Stage 1**. Future stages are out of scope for the MVP design but inform architectural decisions:

1. **Stage 1 (MVP):** Paper-trade swing options on 4 ETFs from a local Mac app
2. **Stage 2:** Add chat interface ("what should I trade today?") with streaming responses
3. **Stage 3:** Expand universe (mega-cap stocks, then optionable scan)
4. **Stage 4:** Lift to cloud hosting (always-on)
5. **Stage 5:** Intraday capability
6. **Stage 6:** Live (real-money) trading with the system as co-pilot

Each subsequent stage gets its own design and implementation cycle.

---

## 3. High-level architecture

A single Python process running on the user's Mac. The user starts it with one command; a browser tab opens at `http://localhost:8000` showing the dashboard. SQLite database file lives next to the app. Nothing in the cloud.

```
┌────────────────────────────────────────────────────────────────────┐
│  Single Python process (FastAPI + APScheduler in-process)          │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Scheduler    │  │ HTTP API     │  │ HTMX dash    │              │
│  │ (APScheduler)│  │ (FastAPI)    │  │ (Jinja+HTMX) │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                       │
│  ┌──────▼─────────────────▼─────────────────▼────────────┐         │
│  │ Service layer (pure Python, async-capable)            │         │
│  │  - Data ingestion (Alpaca, yfinance, FRED, RSS)       │         │
│  │  - Signal generators (technicals, IV/vol)             │         │
│  │  - LLM reasoning (Anthropic Claude API)               │         │
│  │  - Idea validator (allowlist, spread guard, events)   │         │
│  │  - Trade executor (Alpaca paper API)                  │         │
│  │  - Notification dispatcher (Pushover)                 │         │
│  │  - Reconciliation job (Alpaca ↔ local journal)        │         │
│  │  - Backtest/replay engine                             │         │
│  │  - Audit logger                                       │         │
│  └───────────────────────┬───────────────────────────────┘         │
│                          │                                          │
│  ┌───────────────────────▼───────────────────────────────┐         │
│  │ SQLite (WAL mode) — single database file              │         │
│  │  - signals, trade_intents, paper_orders, fills,       │         │
│  │    journal, audit_log, job_locks                      │         │
│  └───────────────────────────────────────────────────────┘         │
└────────────────────────────────────────────────────────────────────┘
       │              │           │            │            │
       ▼              ▼           ▼            ▼            ▼
   ┌─────────┐  ┌─────────┐  ┌──────────┐ ┌─────────┐ ┌──────────┐
   │ Alpaca  │  │ FRED    │  │ News RSS │ │ Pushover│ │ Anthropic│
   │ paper   │  │ econ    │  │ +Finnhub │ │ phone   │ │ Claude   │
   │ + data  │  │ data    │  │ +EDGAR   │ │ push    │ │ API      │
   └─────────┘  └─────────┘  └──────────┘ └─────────┘ └──────────┘
```

### Process discipline (non-negotiable, per architecture review)

- Run with `uvicorn --workers 1` and **no `--reload`** in real mode
- All blocking calls (yfinance, requests, feedparser) wrapped in `loop.run_in_executor`
- A `job_locks` table in SQLite to prevent double-fire on restart mid-cycle
- SQLite opened with `PRAGMA journal_mode=WAL`
- Source of truth for trade state = **Alpaca**. Local journal is denormalized cache; reconciliation job runs after each cycle.

---

## 4. External dependencies

| Service | Purpose | Tier | Verified | Notes |
|---|---|---|---|---|
| Alpaca | Paper trading + stock data + options data fallback | Free Basic | YELLOW | Confirm options data tier is sufficient before lock-in. Use `alpaca-py` SDK. |
| yfinance (lib) | Options chain data (primary) | Free | YELLOW | Fragile; must have Alpaca options data fallback. Add retry + circuit breaker. |
| FRED | Economic data (CPI, jobs, Fed rates) | Free | GREEN | Requires free API key. Use `fredapi` Python package. |
| RSS feeds | Financial headlines | Free | GREEN | Reuters, CNBC, MarketWatch, Yahoo Finance, SEC EDGAR via `feedparser`. ETag/If-Modified-Since support required. |
| Finnhub | Structured news headlines | Free tier | GREEN | 60 calls/min. |
| Pushover | Phone push notifications | $5 one-time per platform | GREEN | iOS app maintained. Use HTTP API. |
| Anthropic Claude API | News/macro reasoning | Pay-per-use | GREEN | Estimate ~$15-30/month with prompt caching. Use the latest Sonnet model (verify exact ID at build time). |
| `pandas_market_calendars` | NYSE calendar (half-days, holidays) | Free | GREEN | Required for correctness — never use naive UTC math. |

**Total estimated ongoing cost:** ~$15-30/month (almost entirely Claude API), one-time ~$5 for Pushover.

---

## 5. Components (what each one does)

Each component is a Python module with a clear interface. Internals can change without breaking consumers.

### 5.1 Data ingestion (`ingest/`)

- `MarketDataClient` — fetches OHLC and current quotes for SPY/QQQ/IWM/DIA. Primary: Alpaca. Fallback: yfinance.
- `OptionsChainClient` — fetches options chains for the four ETFs. Primary: yfinance. Fallback: Alpaca options data.
- `EconomicDataClient` — pulls latest values + release schedule for CPI, NFP, FOMC, Fed funds rate from FRED.
- `NewsClient` — pulls RSS feeds + Finnhub headlines, dedupes by URL hash, stores arrival timestamp (not published timestamp).
- `MarketCalendar` — wraps `pandas_market_calendars`. Authoritative source for "is the market open right now," "next session," "is this a half-day."
- `EventCalendar` — maintains upcoming FOMC, CPI, NFP, and component-leader earnings dates; queryable by "is `symbol` in an event window over the next N days."

### 5.2 Signal generators (`signals/`)

Each signal is a pure function: `(market_state, options_chain, econ_state, news) -> Optional[SignalCandidate]`. Examples for the MVP:

- `TrendMomentumSignal` — multi-timeframe MAs + RSI on the underlying
- `VolatilitySignal` — IV rank, IV percentile, term-structure shape
- `NewsCatalystSignal` — recent headlines passing a relevance filter, surfaced for LLM synthesis

A signal does NOT pick contracts or set strikes. It produces a structured *candidate* that downstream components can act on.

### 5.3 LLM reasoning (`reasoning/`)

`IdeaSynthesizer` — given:
- a set of `SignalCandidate`s active right now
- the current market snapshot (numeric)
- recent news headlines (titles + snippets, with arrival timestamps)
- the event calendar window

…calls Claude with a system prompt that:

- Defines the role ("disciplined options trade-idea generator for SPY/QQQ/IWM/DIA")
- Provides today's data as structured input
- Requires structured JSON output matching `IdeaProposal` schema (ticker, direction, structure, rationale, citations)
- **Forbids the model from emitting raw prices, IVs, strikes, or dates** — those are placeholders the data layer fills in
- Requires every claim to cite a specific signal or news headline by ID

Uses Anthropic prompt caching on the static portion of the prompt. Hard token cap per call.

### 5.4 Idea validator (`validation/`)

Given an `IdeaProposal`, runs a chain of checks before it is shown to the user:

- Ticker is in `{SPY, QQQ, IWM, DIA}` allowlist
- Proposed contract exists in the options chain right now
- Bid-ask spread ≤ 5% of mid (else reject)
- Not in a blocked event window (FOMC/CPI/NFP/earnings) for long-premium strategies
- For positions with expiry ≤ 7 days: not within ±1.5% of strike (pin-risk guard)
- Daily idea count cap not exceeded (default: 2 per market day; counted as "validated ideas surfaced to user," not raw LLM proposals — i.e., if the user already has 2 validated ideas today, further LLM proposals are still synthesized for the audit log but not surfaced or alerted)

Each rejection is logged with reason. Rejected ideas appear in an "audit" view for transparency but are not shown as actionable.

### 5.5 Trade executor (`execution/`)

`PaperExecutor`:
- Generates `client_order_id` deterministically from `(trade_date, symbol, signal_id)` — restart-safe and idempotent
- Submits the order via Alpaca paper API
- Polls for fill, simulates a **realistic-fill price** alongside the actual Alpaca paper fill: worst-side NBBO + 1-tick haircut. Both are recorded.
- Writes `paper_orders` and `fills` rows on every state change
- Honors a global **kill switch** (an `active=false` row in `app_state`) and **daily loss/notional cap** (cumulative paper P&L this session vs configured limit). Both are checked *before* submission.

A separate `Reconciler` runs after each cycle and reconciles Alpaca's view of orders/positions against the local journal; mismatches are logged and surfaced.

### 5.6 Notification dispatcher (`notify/`)

`PushoverDispatcher` — sends a phone push for every new validated idea. Dedupe key per idea so restarts don't double-buzz. Configurable quiet hours.

### 5.7 Web layer (`web/`)

- FastAPI app
- Server-rendered Jinja templates with HTMX for interactivity (no React, no build step)
- TradingView Lightweight Charts loaded via `<script>` tag for price charts
- Routes:
  - `/` — dashboard (today's ideas, open positions, P&L, status banner)
  - `/ideas/<id>` — idea detail; thesis input field; "Execute paper trade" button
  - `/journal` — full history
  - `/retrospective` — **headline screen**: weekly predicted-vs-realized scorecard, broken down by Claude ideas vs user overrides
  - `/backtest` — replay mode UI
  - `/audit` — rejected ideas + LLM prompts/responses
  - `/health` — internal status (data source health, last cycle time, etc.)
  - `/kill` — POST endpoint to flip the kill switch

**UX rule (from gotchas review):** on `/ideas/<id>`, the user MUST type a one-line thesis *before* the LLM rationale is revealed. This is forecast journaling — it forces engagement and lets us measure user calibration vs the system's.

### 5.8 Scheduler (`scheduler/`)

APScheduler running in-process. Jobs:

- `pre_open_scan` — 30 min before market open: refresh econ data, headlines, event calendar
- `mid_morning_scan` — ~10:00 ET: full scan + idea generation
- `midday_scan` — ~13:00 ET: full scan + idea generation (subject to daily cap)
- `post_close_summary` — after market close: reconcile Alpaca, update P&L, mark expired positions, daily summary email/push

Every job acquires a row-level lock in `job_locks` before running and releases on completion.

### 5.9 Backtest / replay (`backtest/`)

`Replayer`:
- Loads historical OHLC + options snapshots + news from a local data archive
- Steps forward in time
- For each step, calls the same signal pipeline + LLM with **only point-in-time data**
- Records what ideas would have been generated, what fills would have occurred (using the realistic-fill model), and the realized P&L
- Reports drawdown-by-quarter and drawdown-in-VIX-spike-regime as first-class metrics
- **Forbids any in-sample tuning**: parameters must be locked before the test window

Required regimes to cover before any live use is enabled in the UI:
- Aug 2024 yen carry unwind (high-vol)
- At least one bear quarter (e.g., Q4 2018, H1 2022)

### 5.10 Audit log (`audit/`)

Append-only `audit_log` table. Records:

- Every LLM prompt + response (with token counts, cost)
- Every order intent (whether or not it became an order)
- Every kill-switch toggle, every daily-cap breach, every config change

Never deleted. Indexable by date and by signal_id.

---

## 6. Data flow (a single cycle)

1. **Scheduler fires** `mid_morning_scan` (after acquiring job lock)
2. **`MarketCalendar.is_open()`** check; if false, exit
3. **`MarketDataClient.snapshot(['SPY','QQQ','IWM','DIA'])`** → quotes + recent OHLC
4. **`OptionsChainClient.chains_for(...)`** → live chains (yfinance, fallback Alpaca)
5. **`NewsClient.fresh_since(last_run)`** → new headlines (with arrival timestamps)
6. **`EconomicDataClient.latest()`** → recent econ data points
7. **Signal generators** run in parallel; each returns 0+ candidates
8. **`IdeaSynthesizer.synthesize(...)`** → calls Claude with structured input; returns 0+ `IdeaProposal`s
9. **`Validator.validate(proposal)`** for each → some accepted, some rejected (logged either way)
10. **For each accepted idea**: persist to `signals` table, push Pushover alert, dashboard auto-refreshes
11. **Reconciler** runs: compares local view of open positions/orders to Alpaca; logs any drift
12. **Audit log** updated for the cycle
13. **Job lock released**

User interaction (independent of the cycle): user opens dashboard, reviews idea, types thesis, clicks "Execute paper trade." The HTTP handler calls `PaperExecutor.submit(idea, thesis)`, which checks kill switch + daily caps, generates `client_order_id`, submits to Alpaca, records intent + fill in journal.

---

## 7. Error handling and degradation

- **Alpaca outage** → trade execution is disabled; banner shown in UI; ideas can still be generated (without execution path)
- **yfinance failure** → automatic fallback to Alpaca options data; if both fail, options-dependent signals are skipped this cycle, banner shown
- **FRED outage** → econ data goes stale; signals continue with cached values; banner shown after staleness threshold
- **News fetch failure** → degrade to "no fresh news this cycle"; LLM still runs with technicals + econ
- **Anthropic API failure** → cycle generates no LLM ideas this round; mechanical signals still surface as "raw signals" in audit view; no alerts fired
- **Pushover failure** → alert is queued in DB and retried; dashboard shows undelivered alerts
- **SQLite lock** → exponential backoff; logged; user-facing banner if persistent
- **Kill switch flipped or daily loss cap hit** → executor refuses all new orders; UI shows STOPPED banner; ideas still generated and journaled but not actionable

Every degraded mode is visible in the dashboard status banner. The user is never left wondering "is it broken?"

---

## 8. Testing

### 8.1 Unit tests

- Signal computations (deterministic, table-driven)
- Validator rules (each rejection reason has a test)
- `client_order_id` derivation (stable across restarts)
- Realistic-fill model math
- Idempotency of executor (submitting the same intent twice produces one order)
- Audit log write semantics

### 8.2 Integration tests (with mocked external APIs)

- Full cycle: data → signals → LLM (mocked) → validation → idea persisted → notification queued
- Reconciliation: local state diverges from "Alpaca" — drift detected and logged
- Job lock: simulated mid-cycle kill, restart does not double-fire
- Degraded modes: each external dependency failure surfaces correct banner
- Schema validation on LLM output: malformed JSON, hallucinated ticker, missing citation

### 8.3 Replay-mode tests

- Run replay over a known historical week; assert reproducibility (same data + same signal version → same ideas)
- Assert no future data ever leaks into the LLM prompt (regression test against lookahead bias)

### 8.4 Smoke / acceptance

- Fresh install on a clean Mac: runs from one command, dashboard reachable, one cycle completes against real (free) APIs
- Pushover delivers a test message
- A paper trade can be placed end-to-end through the UI

---

## 9. Security / secrets / config

- All API keys in `~/.config/trading-assistant/.env` (or a similar OS-appropriate path), `chmod 600`
- Never written to logs, never written to SQLite
- Config (idea cap, daily loss cap, quiet hours, etc.) in a YAML file at the same path
- `paper` vs `live` mode is a config flag with a **bright red UI banner** when `live`; MVP refuses to run in `live` mode (a future stage will enable it)

---

## 10. Open questions / deferred decisions

These are explicitly deferred and called out so they do not block the MVP but must be resolved before the corresponding stage:

- **Eventual brokerage for live trading** (Stage 6) — Alpaca live? Tradier? IBKR? Defer until Stage 4 cloud lift is approved.
- **Capital sizing for live** (Stage 6) — depends on Pattern Day Trader rule applicability ($25k threshold) which depends on whether intraday is enabled. Defer.
- **Quiet hours default** for Pushover — to be set during MVP delivery based on user time-zone.
- **Exact Sonnet model ID** to use for `IdeaSynthesizer` — verify the latest Sonnet model on Anthropic's models page at build time.
- **Backtest data archive sourcing** — historical options data is the hard bit; may need to use OptionsDX, Polygon's flat-file archive, or scraped CBOE data. Decide during implementation.

---

## 11. Definition of done for MVP

The MVP is done when, on a clean Mac:

1. Installation is a single command, takes under 5 minutes, requires no developer tooling beyond Homebrew + Python.
2. The user can paper-trade for two consecutive weeks without an unrecovered crash.
3. The system has produced ≤ 2 ideas per market day, each with structured reasoning, citations, and validator pass.
4. Every paper trade has a recorded `client_order_id`, an "Alpaca paper fill," a "realistic-fill estimate," and an outcome.
5. The weekly retrospective screen renders correctly with at least 5 closed trades.
6. Replay mode reproduces a chosen historical week deterministically and surfaces zero future-data leaks in the audit log.
7. Pushover alerts deliver to the user's phone.
8. Kill switch and daily loss cap both verified working.
