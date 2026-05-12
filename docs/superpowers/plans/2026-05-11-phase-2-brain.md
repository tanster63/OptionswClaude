# Phase 2 — Brain (Signals → Idea Synthesis → Validation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the raw market/news/econ data Phase 1 collects into 0–2 validated, paper-tradeable options-trade ideas per cycle, each with a structured thesis the user can review before executing.

**Architecture:** Pipeline of four stages running on top of the Phase 1 ingestion layer:
1. **Signal generators** (`signals/`) — pure functions that read recent ingested state and emit normalized `Signal` rows (e.g. "QQQ_breakout_up", "SPY_iv_rank_85", "FOMC_in_3_days").
2. **`IdeaSynthesizer`** (`brain/synthesizer.py`) — assembles all active signals + a market snapshot + recent news into a single prompt, calls Claude with prompt caching + a hard token cap, parses structured JSON into `TradeIntent` candidates.
3. **`Validator`** (`brain/validator.py`) — runs each candidate through a chain of guards (spread, pin-risk, event-window, idea-cap, daily-loss-cap); records every accept and reject to the audit log.
4. **CLI `synthesize` command** — drives the whole pipeline end-to-end and prints the validated intents.

Phase 2 stops short of executing anything — that's Phase 4. End of Phase 2: the user can run a command and see "here are 0–2 ideas, here's the thesis, here's why they passed." Nothing is sent to Alpaca.

**Tech Stack additions on top of Phase 1:**
- `anthropic` Python SDK (≥0.39) for Claude API
- `pandas` (already pulled in transitively) for OHLCV bar math in `TechnicalSignalGen`
- No new external services beyond Anthropic — Alpaca historical bars come from the SDK we already pinned

**Discipline reminders (carried over from Phase 1):**
- TDD: failing test → minimal implementation → passing test → commit. One test, one commit, at a time.
- Protocols for all external dependencies (Anthropic, Alpaca bars) so tests can inject fakes.
- Every rejection has its own named reason and its own test.
- LLM output must be parsed through a strict pydantic model — never trust the raw string.
- Cost discipline: hard token cap per Claude call, prompt caching on static parts, structured logging of token usage.

---

## File Structure

```
src/trading_assistant/
  signals/
    __init__.py
    model.py              # Signal, SignalKind enum, evidence shapes
    repo.py               # SignalRepo (write, list_since, list_active)
    protocol.py           # SignalGenerator Protocol
    news.py               # NewsSignalGen
    technical.py          # TechnicalSignalGen
    volatility.py         # VolatilitySignalGen
    event_proximity.py    # EventProximitySignalGen
  ingest/
    bars.py               # Bar dataclass + BarSource Protocol
  adapters/
    alpaca.py             # extend with AlpacaBarsAdapter
  intents/
    __init__.py
    model.py              # TradeIntent, Leg, Strategy enum
    repo.py               # TradeIntentRepo
  brain/
    __init__.py
    anthropic_client.py   # AnthropicClient (thin wrapper)
    synthesizer.py        # IdeaSynthesizer
    validator.py          # Validator + GuardResult + run_guards
    guards/
      __init__.py
      spread.py           # SpreadGuard
      pin_risk.py         # PinRiskGuard
      event_window.py     # EventWindowGuard
      caps.py             # IdeaCapGuard + DailyLossCapGuard
  cli.py                  # extend with `synthesize` command

tests/
  test_signals_model.py
  test_signals_repo.py
  test_signals_news.py
  test_signals_technical.py
  test_signals_volatility.py
  test_signals_event_proximity.py
  test_ingest_bars.py
  test_intents_model.py
  test_intents_repo.py
  test_brain_anthropic_client.py
  test_brain_synthesizer.py
  test_brain_validator.py
  test_guards_spread.py
  test_guards_pin_risk.py
  test_guards_event_window.py
  test_guards_caps.py
  test_cli_synthesize.py
```

---

## Task 0: Add `anthropic` dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the dependency**

Edit `pyproject.toml`. In the `[project] dependencies` array, add:

```toml
    "anthropic>=0.39,<0.50",
```

- [ ] **Step 2: Sync the lockfile and verify import works**

```bash
uv sync
uv run python -c "import anthropic; print(anthropic.__version__)"
```

Expected: prints a version string `0.39.x` or higher.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add anthropic SDK dependency for Phase 2 brain"
```

---

## Task 1: `Signal` model + `SignalKind` enum

**Files:**
- Create: `src/trading_assistant/signals/__init__.py` (empty)
- Create: `src/trading_assistant/signals/model.py`
- Create: `tests/test_signals_model.py`

A `Signal` is a normalized "something interesting happened" record. Every generator emits the same shape so the synthesizer can iterate over them uniformly.

- [ ] **Step 1: Write the failing test**

`tests/test_signals_model.py`:

```python
"""Signal model tests."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from trading_assistant.signals.model import Signal, SignalKind


def test_signal_round_trip_through_json():
    s = Signal(
        id="abc123",
        kind=SignalKind.TECHNICAL_BREAKOUT,
        symbol="QQQ",
        created_at=dt.datetime(2026, 5, 11, 14, 30, tzinfo=dt.timezone.utc),
        strength=0.7,
        evidence={"close": 712.5, "20d_high": 711.0},
    )
    raw = s.model_dump_json()
    parsed = Signal.model_validate_json(raw)
    assert parsed == s


def test_signal_strength_must_be_between_zero_and_one():
    with pytest.raises(ValidationError):
        Signal(
            id="x",
            kind=SignalKind.TECHNICAL_BREAKOUT,
            symbol="QQQ",
            created_at=dt.datetime.now(dt.timezone.utc),
            strength=1.5,
            evidence={},
        )


def test_signal_symbol_uppercased():
    s = Signal(
        id="x",
        kind=SignalKind.TECHNICAL_BREAKOUT,
        symbol="spy",
        created_at=dt.datetime.now(dt.timezone.utc),
        strength=0.5,
        evidence={},
    )
    assert s.symbol == "SPY"


def test_signal_kind_values():
    assert SignalKind.NEWS_CATALYST.value == "news_catalyst"
    assert SignalKind.TECHNICAL_BREAKOUT.value == "technical_breakout"
    assert SignalKind.VOLATILITY_REGIME.value == "volatility_regime"
    assert SignalKind.EVENT_PROXIMITY.value == "event_proximity"
```

- [ ] **Step 2: Run the test, watch it fail**

```bash
uv run pytest tests/test_signals_model.py -v
```

Expected: ImportError for `trading_assistant.signals.model`.

- [ ] **Step 3: Implement the minimum**

Create `src/trading_assistant/signals/__init__.py` (empty file).

Create `src/trading_assistant/signals/model.py`:

```python
"""Normalized signal record produced by all signal generators."""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class SignalKind(str, Enum):
    NEWS_CATALYST = "news_catalyst"
    TECHNICAL_BREAKOUT = "technical_breakout"
    VOLATILITY_REGIME = "volatility_regime"
    EVENT_PROXIMITY = "event_proximity"


class Signal(BaseModel):
    """A normalized 'something is happening' record. One row per emission."""

    id: str
    kind: SignalKind
    symbol: str
    created_at: dt.datetime
    strength: float = Field(ge=0.0, le=1.0)
    evidence: dict[str, Any]

    @field_validator("symbol")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()
```

- [ ] **Step 4: Run the test, watch it pass**

```bash
uv run pytest tests/test_signals_model.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/trading_assistant/signals/__init__.py \
        src/trading_assistant/signals/model.py \
        tests/test_signals_model.py
git commit -m "feat(signals): add Signal model and SignalKind enum"
```

---

## Task 2: `SignalRepo` — persist and query signals

**Files:**
- Create: `src/trading_assistant/signals/repo.py`
- Create: `tests/test_signals_repo.py`

- [ ] **Step 1: Write the failing test**

`tests/test_signals_repo.py`:

```python
"""SignalRepo tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.db.schema import create_schema
from trading_assistant.signals.model import Signal, SignalKind
from trading_assistant.signals.repo import SignalRepo


def _make(symbol: str, created_at: dt.datetime, kind: SignalKind = SignalKind.NEWS_CATALYST) -> Signal:
    return Signal(
        id=f"{symbol}-{created_at.isoformat()}",
        kind=kind,
        symbol=symbol,
        created_at=created_at,
        strength=0.5,
        evidence={"note": "test"},
    )


def test_write_and_round_trip(db_conn):
    create_schema(db_conn)
    repo = SignalRepo(db_conn)
    now = dt.datetime(2026, 5, 11, 14, 0, tzinfo=dt.timezone.utc)
    s = _make("SPY", now)
    repo.write(s)
    fetched = repo.list_since(now - dt.timedelta(minutes=1))
    assert len(fetched) == 1
    assert fetched[0] == s


def test_list_since_respects_cutoff(db_conn):
    create_schema(db_conn)
    repo = SignalRepo(db_conn)
    old = dt.datetime(2026, 5, 11, 10, 0, tzinfo=dt.timezone.utc)
    new = dt.datetime(2026, 5, 11, 14, 0, tzinfo=dt.timezone.utc)
    repo.write(_make("SPY", old))
    repo.write(_make("QQQ", new))
    out = repo.list_since(dt.datetime(2026, 5, 11, 12, 0, tzinfo=dt.timezone.utc))
    assert [s.symbol for s in out] == ["QQQ"]


def test_write_is_idempotent_on_id(db_conn):
    create_schema(db_conn)
    repo = SignalRepo(db_conn)
    s = _make("SPY", dt.datetime(2026, 5, 11, 14, 0, tzinfo=dt.timezone.utc))
    repo.write(s)
    repo.write(s)  # second write is a no-op
    assert len(repo.list_since(s.created_at - dt.timedelta(minutes=1))) == 1
```

- [ ] **Step 2: Run the test, watch it fail**

```bash
uv run pytest tests/test_signals_repo.py -v
```

Expected: ImportError for `SignalRepo`.

- [ ] **Step 3: Implement the minimum**

Create `src/trading_assistant/signals/repo.py`:

```python
"""Persistence for Signal rows."""

from __future__ import annotations

import datetime as dt
import json
import sqlite3

from trading_assistant.signals.model import Signal, SignalKind


class SignalRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def write(self, signal: Signal) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO signals(id, created_at, kind, symbol, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                signal.id,
                signal.created_at.isoformat(),
                signal.kind.value,
                signal.symbol,
                json.dumps({"strength": signal.strength, "evidence": signal.evidence}),
            ),
        )
        self._conn.commit()

    def list_since(self, cutoff: dt.datetime) -> list[Signal]:
        rows = self._conn.execute(
            """
            SELECT id, created_at, kind, symbol, payload_json
            FROM signals
            WHERE created_at >= ?
            ORDER BY created_at ASC
            """,
            (cutoff.isoformat(),),
        ).fetchall()
        out: list[Signal] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            out.append(
                Signal(
                    id=row["id"],
                    kind=SignalKind(row["kind"]),
                    symbol=row["symbol"],
                    created_at=dt.datetime.fromisoformat(row["created_at"]),
                    strength=payload["strength"],
                    evidence=payload["evidence"],
                )
            )
        return out
```

- [ ] **Step 4: Run the test, watch it pass**

```bash
uv run pytest tests/test_signals_repo.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/trading_assistant/signals/repo.py tests/test_signals_repo.py
git commit -m "feat(signals): add SignalRepo for persistence and querying"
```

---

## Task 3: `SignalGenerator` Protocol

**Files:**
- Create: `src/trading_assistant/signals/protocol.py`

This is a structural-typing contract that every concrete generator implements. No test needed for the Protocol itself; the concrete generators in later tasks are the real tests.

- [ ] **Step 1: Create the protocol module**

```python
"""Structural contract every signal generator implements."""

from __future__ import annotations

import datetime as dt
from typing import Protocol

from trading_assistant.signals.model import Signal


class SignalGenerator(Protocol):
    name: str

    def generate(self, now: dt.datetime) -> list[Signal]:
        """Read whatever state it needs and return 0+ signals valid at ``now``.

        Implementations must be pure with respect to wall-clock time: they take
        ``now`` as input rather than reading the system clock. This makes them
        reproducible in tests and in the backtest replay engine (Phase 5).
        """
        ...
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
uv run python -c "from trading_assistant.signals.protocol import SignalGenerator; print(SignalGenerator)"
```

Expected: prints `<class 'trading_assistant.signals.protocol.SignalGenerator'>` (or similar typing-module representation).

- [ ] **Step 3: Commit**

```bash
git add src/trading_assistant/signals/protocol.py
git commit -m "feat(signals): add SignalGenerator Protocol"
```

---

## Task 4: `NewsSignalGen` — surface recent news for the universe

**Files:**
- Create: `src/trading_assistant/signals/news.py`
- Create: `tests/test_signals_news.py`

This generator reads news rows arrived in the last N minutes and tags each one with the underlyings whose name appears in the title. It doesn't try to be clever — string match against the configured universe + a small alias map ("Powell" → SPY/QQQ for FOMC speeches). The LLM does the real reasoning later; this generator just surfaces the items.

- [ ] **Step 1: Write the failing test**

`tests/test_signals_news.py`:

```python
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
```

- [ ] **Step 2: Run the test, watch it fail**

```bash
uv run pytest tests/test_signals_news.py -v
```

Expected: ImportError for `NewsSignalGen`.

- [ ] **Step 3: Implement the minimum**

Create `src/trading_assistant/signals/news.py`:

```python
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
```

- [ ] **Step 4: Run the test, watch it pass**

```bash
uv run pytest tests/test_signals_news.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/trading_assistant/signals/news.py tests/test_signals_news.py
git commit -m "feat(signals): add NewsSignalGen with universe + alias matching"
```

---

## Task 5: `Bar` dataclass + `BarSource` Protocol + Alpaca adapter

**Files:**
- Create: `src/trading_assistant/ingest/bars.py`
- Modify: `src/trading_assistant/adapters/alpaca.py`
- Create: `tests/test_ingest_bars.py`

The technical signal generator needs historical OHLCV bars (open/high/low/close/volume per period — typically daily candles). Phase 1 only fetched current quotes; we need to add a bar source. Alpaca's `StockHistoricalDataClient.get_stock_bars` is the primary; for tests we inject a fake.

- [ ] **Step 1: Write the failing test**

`tests/test_ingest_bars.py`:

```python
"""Bar dataclass and BarSource Protocol tests."""

from __future__ import annotations

import datetime as dt

import pytest

from trading_assistant.ingest.bars import Bar, BarSource


def test_bar_is_frozen_dataclass():
    b = Bar(
        symbol="SPY",
        ts=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
        open=738.0,
        high=740.0,
        low=735.0,
        close=739.0,
        volume=1_000_000.0,
    )
    with pytest.raises(Exception):
        b.close = 999.0  # frozen


def test_bar_source_is_protocol():
    class _Fake:
        def daily_bars(self, symbol: str, start: dt.date, end: dt.date) -> list[Bar]:
            return []

    fake: BarSource = _Fake()
    assert fake.daily_bars("SPY", dt.date(2026, 1, 1), dt.date(2026, 5, 11)) == []
```

- [ ] **Step 2: Run the test, watch it fail**

```bash
uv run pytest tests/test_ingest_bars.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `Bar` + `BarSource`**

Create `src/trading_assistant/ingest/bars.py`:

```python
"""Historical OHLCV bar abstraction."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Bar:
    symbol: str
    ts: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class BarSource(Protocol):
    def daily_bars(self, symbol: str, start: dt.date, end: dt.date) -> list[Bar]:
        """Return daily OHLCV bars in chronological order, inclusive on both ends."""
        ...
```

- [ ] **Step 4: Run the test, watch it pass**

```bash
uv run pytest tests/test_ingest_bars.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Extend the Alpaca adapter**

In `src/trading_assistant/adapters/alpaca.py`, add at the bottom (after the existing classes):

```python
class AlpacaBarsAdapter:
    """Daily bars via Alpaca's historical data client."""

    def __init__(self, api_key: str, secret_key: str) -> None:
        from alpaca.data.historical import StockHistoricalDataClient

        self._client = StockHistoricalDataClient(api_key, secret_key)

    def daily_bars(self, symbol: str, start: dt.date, end: dt.date) -> list[Bar]:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=dt.datetime.combine(start, dt.time.min, tzinfo=dt.timezone.utc),
            end=dt.datetime.combine(end, dt.time.max, tzinfo=dt.timezone.utc),
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
```

Make sure these imports exist at the top of `alpaca.py`:

```python
import datetime as dt

from trading_assistant.ingest.bars import Bar
```

(Don't duplicate if already present.)

- [ ] **Step 6: Run all tests to confirm nothing regressed**

```bash
uv run pytest -q
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/trading_assistant/ingest/bars.py \
        src/trading_assistant/adapters/alpaca.py \
        tests/test_ingest_bars.py
git commit -m "feat(ingest): add Bar/BarSource + AlpacaBarsAdapter for historical OHLCV"
```

---

## Task 6: `TechnicalSignalGen` — SMA cross, RSI, breakout

**Files:**
- Create: `src/trading_assistant/signals/technical.py`
- Create: `tests/test_signals_technical.py`

Three classical indicators (kept deliberately simple — this is not where the edge comes from):
- **SMA20 vs SMA50 cross**: when 20-day simple moving average crosses above 50, emit `TECHNICAL_BREAKOUT` bullish. Cross below → bearish.
- **RSI(14)**: overbought (>70) and oversold (<30) emit signals with opposite strengths.
- **20-day high/low breakout**: close above 20-day high → bullish; below 20-day low → bearish.

- [ ] **Step 1: Write the failing test**

`tests/test_signals_technical.py`:

```python
"""TechnicalSignalGen tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.ingest.bars import Bar
from trading_assistant.signals.model import SignalKind
from trading_assistant.signals.technical import TechnicalSignalGen


class _FakeBars:
    def __init__(self, bars_by_symbol: dict[str, list[Bar]]) -> None:
        self._bars = bars_by_symbol

    def daily_bars(self, symbol: str, start: dt.date, end: dt.date) -> list[Bar]:
        return list(self._bars.get(symbol, []))


def _bar(day: int, close: float, symbol: str = "SPY") -> Bar:
    return Bar(
        symbol=symbol,
        ts=dt.datetime(2026, 4, day, tzinfo=dt.timezone.utc),
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=1_000_000.0,
    )


def _flat_bars(symbol: str, days: int, base: float) -> list[Bar]:
    return [_bar(d, base, symbol) for d in range(1, days + 1)]


def test_emits_breakout_when_close_exceeds_20d_high():
    bars = _flat_bars("SPY", 20, 700.0)
    bars.append(_bar(21, 720.0))  # breakout
    gen = TechnicalSignalGen(bar_source=_FakeBars({"SPY": bars}), universe=["SPY"])
    signals = gen.generate(dt.datetime(2026, 4, 21, tzinfo=dt.timezone.utc))
    kinds = [s.kind for s in signals]
    assert SignalKind.TECHNICAL_BREAKOUT in kinds
    breakout = next(s for s in signals if s.kind == SignalKind.TECHNICAL_BREAKOUT)
    assert breakout.symbol == "SPY"
    assert breakout.evidence["direction"] == "up"


def test_no_breakout_when_close_is_within_range():
    bars = _flat_bars("SPY", 20, 700.0)
    bars.append(_bar(21, 700.5))
    gen = TechnicalSignalGen(bar_source=_FakeBars({"SPY": bars}), universe=["SPY"])
    signals = gen.generate(dt.datetime(2026, 4, 21, tzinfo=dt.timezone.utc))
    assert all(s.kind != SignalKind.TECHNICAL_BREAKOUT for s in signals)


def test_returns_empty_when_too_few_bars():
    gen = TechnicalSignalGen(
        bar_source=_FakeBars({"SPY": _flat_bars("SPY", 5, 700.0)}),
        universe=["SPY"],
    )
    assert gen.generate(dt.datetime(2026, 4, 5, tzinfo=dt.timezone.utc)) == []


def test_handles_missing_symbol_gracefully():
    gen = TechnicalSignalGen(bar_source=_FakeBars({}), universe=["SPY"])
    assert gen.generate(dt.datetime(2026, 4, 21, tzinfo=dt.timezone.utc)) == []
```

- [ ] **Step 2: Run the test, watch it fail**

```bash
uv run pytest tests/test_signals_technical.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement the generator**

Create `src/trading_assistant/signals/technical.py`:

```python
"""Technical signal generator: SMA cross, RSI, breakout."""

from __future__ import annotations

import datetime as dt
import hashlib
from statistics import fmean

from trading_assistant.ingest.bars import Bar, BarSource
from trading_assistant.signals.model import Signal, SignalKind

_LOOKBACK_DAYS = 60  # enough for 50-day SMA + 14-day RSI + breakout buffer


class TechnicalSignalGen:
    name = "technical"

    def __init__(self, bar_source: BarSource, universe: list[str]) -> None:
        self._bars = bar_source
        self._universe = [u.upper() for u in universe]

    def generate(self, now: dt.datetime) -> list[Signal]:
        out: list[Signal] = []
        start = (now - dt.timedelta(days=_LOOKBACK_DAYS * 2)).date()
        end = now.date()
        for symbol in self._universe:
            bars = self._bars.daily_bars(symbol, start, end)
            if len(bars) < 21:
                continue
            closes = [b.close for b in bars]
            out.extend(self._breakout(symbol, closes, now))
            out.extend(self._sma_cross(symbol, closes, now))
            out.extend(self._rsi(symbol, closes, now))
        return out

    def _breakout(self, symbol: str, closes: list[float], now: dt.datetime) -> list[Signal]:
        window = closes[-21:-1]  # last 20 closes excluding today
        today_close = closes[-1]
        hi = max(window)
        lo = min(window)
        if today_close > hi:
            return [self._sig(symbol, SignalKind.TECHNICAL_BREAKOUT, 0.7, now,
                               {"direction": "up", "close": today_close, "20d_high": hi})]
        if today_close < lo:
            return [self._sig(symbol, SignalKind.TECHNICAL_BREAKOUT, 0.7, now,
                               {"direction": "down", "close": today_close, "20d_low": lo})]
        return []

    def _sma_cross(self, symbol: str, closes: list[float], now: dt.datetime) -> list[Signal]:
        if len(closes) < 51:
            return []
        sma20_today = fmean(closes[-20:])
        sma50_today = fmean(closes[-50:])
        sma20_yest = fmean(closes[-21:-1])
        sma50_yest = fmean(closes[-51:-1])
        crossed_up = sma20_yest <= sma50_yest and sma20_today > sma50_today
        crossed_dn = sma20_yest >= sma50_yest and sma20_today < sma50_today
        if crossed_up:
            return [self._sig(symbol, SignalKind.TECHNICAL_BREAKOUT, 0.6, now,
                               {"direction": "up", "indicator": "sma20_over_sma50"})]
        if crossed_dn:
            return [self._sig(symbol, SignalKind.TECHNICAL_BREAKOUT, 0.6, now,
                               {"direction": "down", "indicator": "sma20_under_sma50"})]
        return []

    def _rsi(self, symbol: str, closes: list[float], now: dt.datetime) -> list[Signal]:
        if len(closes) < 15:
            return []
        deltas = [closes[i] - closes[i - 1] for i in range(-14, 0)]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        avg_gain = sum(gains) / 14 if gains else 0.0
        avg_loss = sum(losses) / 14 if losses else 0.0
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
        if rsi > 70:
            return [self._sig(symbol, SignalKind.TECHNICAL_BREAKOUT, 0.4, now,
                               {"direction": "down", "indicator": "rsi_overbought", "rsi": rsi})]
        if rsi < 30:
            return [self._sig(symbol, SignalKind.TECHNICAL_BREAKOUT, 0.4, now,
                               {"direction": "up", "indicator": "rsi_oversold", "rsi": rsi})]
        return []

    @staticmethod
    def _sig(symbol: str, kind: SignalKind, strength: float, now: dt.datetime,
             evidence: dict) -> Signal:
        key = f"tech:{symbol}:{kind.value}:{evidence.get('indicator', evidence.get('direction', ''))}:{now.date().isoformat()}"
        sid = "tech_" + hashlib.sha256(key.encode()).hexdigest()[:16]
        return Signal(
            id=sid,
            kind=kind,
            symbol=symbol,
            created_at=now,
            strength=strength,
            evidence=evidence,
        )
```

- [ ] **Step 4: Run the test, watch it pass**

```bash
uv run pytest tests/test_signals_technical.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/trading_assistant/signals/technical.py tests/test_signals_technical.py
git commit -m "feat(signals): add TechnicalSignalGen with SMA cross, RSI, breakout"
```

---

## Task 7: `VolatilitySignalGen` — IV rank from options chain

**Files:**
- Create: `src/trading_assistant/signals/volatility.py`
- Create: `tests/test_signals_volatility.py`

**Context on IV rank (for the non-trading reader):** Implied volatility (IV) is the market's bet on how much a stock will move. "IV rank" puts today's IV on a 0–100 scale relative to its trailing 1-year range: 100 = IV is at its 1-year high, 0 = at the 1-year low. High IV → options are expensive → favors selling-premium strategies. Low IV → options are cheap → favors buying premium. For MVP we approximate by taking the median ATM IV across all expiries in the chain and comparing to a historical IV series we persist. For Phase 2 we just emit the current IV-rank signal — building the historical IV series is a Phase 3 enhancement.

This task uses a simpler proxy: median ATM IV in the chain right now, classified as `low` (<0.15), `normal` (0.15–0.25), `high` (>0.25). The thresholds are coarse; we'll learn what's right from the retrospective in Phase 4.

- [ ] **Step 1: Write the failing test**

`tests/test_signals_volatility.py`:

```python
"""VolatilitySignalGen tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.ingest.options_chain import OptionContract
from trading_assistant.signals.model import SignalKind
from trading_assistant.signals.volatility import VolatilitySignalGen


class _FakeChains:
    def __init__(self, by_symbol: dict[str, list[OptionContract]]) -> None:
        self._chains = by_symbol

    def chain(self, symbol: str) -> list[OptionContract]:
        return list(self._chains.get(symbol, []))


class _FakeQuotes:
    def __init__(self, mids: dict[str, float]) -> None:
        self._mids = mids

    def snapshot(self, symbols: list[str]) -> dict:
        from trading_assistant.ingest.market_data import Quote

        out = {}
        for s in symbols:
            m = self._mids.get(s)
            if m is None:
                continue
            out[s] = Quote(symbol=s, bid=m - 0.05, ask=m + 0.05, last=m,
                           ts=dt.datetime.now(dt.timezone.utc), source="fake")
        return out


def _opt(strike: float, iv: float, right: str = "C", days_to_exp: int = 30) -> OptionContract:
    return OptionContract(
        occ_symbol=f"X{strike}{right}",
        underlying="SPY",
        expiry=(dt.datetime(2026, 5, 11) + dt.timedelta(days=days_to_exp)).date(),
        strike=strike,
        right=right,
        bid=1.0,
        ask=1.1,
        last=1.05,
        iv=iv,
    )


def test_emits_high_iv_signal_when_median_atm_iv_above_threshold():
    chain = [_opt(700, 0.30), _opt(710, 0.32), _opt(720, 0.28)]
    gen = VolatilitySignalGen(
        chain_client=_FakeChains({"SPY": chain}),
        quote_client=_FakeQuotes({"SPY": 710.0}),
        universe=["SPY"],
    )
    signals = gen.generate(dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    assert len(signals) == 1
    assert signals[0].kind == SignalKind.VOLATILITY_REGIME
    assert signals[0].evidence["regime"] == "high"


def test_emits_low_iv_signal_when_median_atm_iv_below_threshold():
    chain = [_opt(700, 0.10), _opt(710, 0.12), _opt(720, 0.11)]
    gen = VolatilitySignalGen(
        chain_client=_FakeChains({"SPY": chain}),
        quote_client=_FakeQuotes({"SPY": 710.0}),
        universe=["SPY"],
    )
    signals = gen.generate(dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    assert len(signals) == 1
    assert signals[0].evidence["regime"] == "low"


def test_no_signal_in_normal_regime():
    chain = [_opt(700, 0.20), _opt(710, 0.18), _opt(720, 0.22)]
    gen = VolatilitySignalGen(
        chain_client=_FakeChains({"SPY": chain}),
        quote_client=_FakeQuotes({"SPY": 710.0}),
        universe=["SPY"],
    )
    assert gen.generate(dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc)) == []


def test_empty_chain_returns_no_signal():
    gen = VolatilitySignalGen(
        chain_client=_FakeChains({}),
        quote_client=_FakeQuotes({"SPY": 710.0}),
        universe=["SPY"],
    )
    assert gen.generate(dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc)) == []
```

- [ ] **Step 2: Run the test, watch it fail**

```bash
uv run pytest tests/test_signals_volatility.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement the generator**

Create `src/trading_assistant/signals/volatility.py`:

```python
"""Volatility regime signal generator.

Reads the current options chain and classifies median ATM IV as low/normal/high.
ATM is approximated as the 5 strikes nearest to the underlying mid quote.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from statistics import median
from typing import Protocol

from trading_assistant.ingest.market_data import Quote
from trading_assistant.ingest.options_chain import OptionContract
from trading_assistant.signals.model import Signal, SignalKind

_LOW_IV = 0.15
_HIGH_IV = 0.25
_ATM_WINDOW = 5


class _ChainClient(Protocol):
    def chain(self, symbol: str) -> list[OptionContract]: ...


class _QuoteClient(Protocol):
    def snapshot(self, symbols: list[str]) -> dict[str, Quote]: ...


class VolatilitySignalGen:
    name = "volatility"

    def __init__(self, chain_client: _ChainClient, quote_client: _QuoteClient,
                 universe: list[str]) -> None:
        self._chain = chain_client
        self._quote = quote_client
        self._universe = [u.upper() for u in universe]

    def generate(self, now: dt.datetime) -> list[Signal]:
        out: list[Signal] = []
        quotes = self._quote.snapshot(self._universe)
        for symbol in self._universe:
            q = quotes.get(symbol)
            if q is None:
                continue
            mid = (q.bid + q.ask) / 2.0
            chain = self._chain.chain(symbol)
            if not chain:
                continue
            atm = sorted(chain, key=lambda c: abs(c.strike - mid))[:_ATM_WINDOW]
            ivs = [c.iv for c in atm if c.iv is not None and c.iv > 0]
            if not ivs:
                continue
            med = median(ivs)
            regime: str | None
            if med >= _HIGH_IV:
                regime = "high"
            elif med <= _LOW_IV:
                regime = "low"
            else:
                regime = None
            if regime is None:
                continue
            out.append(self._sig(symbol, regime, med, now))
        return out

    @staticmethod
    def _sig(symbol: str, regime: str, iv: float, now: dt.datetime) -> Signal:
        key = f"vol:{symbol}:{regime}:{now.date().isoformat()}"
        sid = "vol_" + hashlib.sha256(key.encode()).hexdigest()[:16]
        return Signal(
            id=sid,
            kind=SignalKind.VOLATILITY_REGIME,
            symbol=symbol,
            created_at=now,
            strength=0.5,
            evidence={"regime": regime, "median_atm_iv": iv},
        )
```

- [ ] **Step 4: Run the test, watch it pass**

```bash
uv run pytest tests/test_signals_volatility.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/trading_assistant/signals/volatility.py tests/test_signals_volatility.py
git commit -m "feat(signals): add VolatilitySignalGen with low/high IV regime detection"
```

---

## Task 8: `EventProximitySignalGen` — surface upcoming FOMC/CPI/NFP

**Files:**
- Create: `src/trading_assistant/signals/event_proximity.py`
- Create: `tests/test_signals_event_proximity.py`

Reads the `EventCalendar` from Phase 1 and emits one signal per universe symbol with events in the next 5 calendar days.

- [ ] **Step 1: Write the failing test**

`tests/test_signals_event_proximity.py`:

```python
"""EventProximitySignalGen tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.calendars.events import EconomicEvent, EventCalendar, EventKind
from trading_assistant.signals.event_proximity import EventProximitySignalGen
from trading_assistant.signals.model import SignalKind


def test_emits_signal_when_event_within_window():
    cal = EventCalendar(events=[
        EconomicEvent(
            kind=EventKind.FOMC,
            date=dt.date(2026, 5, 14),
            symbols=frozenset({"SPY", "QQQ"}),
        ),
    ])
    gen = EventProximitySignalGen(
        calendar=cal,
        universe=["SPY", "QQQ", "IWM", "DIA"],
        window_days=5,
    )
    sigs = gen.generate(dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    symbols = {s.symbol for s in sigs}
    assert symbols == {"SPY", "QQQ"}
    spy_sig = next(s for s in sigs if s.symbol == "SPY")
    assert spy_sig.kind == SignalKind.EVENT_PROXIMITY
    assert spy_sig.evidence["event_kind"] == "fomc"
    assert spy_sig.evidence["days_until"] == 3


def test_no_signal_when_no_event_in_window():
    cal = EventCalendar(events=[
        EconomicEvent(
            kind=EventKind.FOMC,
            date=dt.date(2026, 6, 14),
            symbols=frozenset({"SPY"}),
        ),
    ])
    gen = EventProximitySignalGen(calendar=cal, universe=["SPY"], window_days=5)
    assert gen.generate(dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc)) == []


def test_no_signal_for_symbols_outside_universe():
    cal = EventCalendar(events=[
        EconomicEvent(
            kind=EventKind.EARNINGS,
            date=dt.date(2026, 5, 12),
            symbols=frozenset({"NVDA"}),
        ),
    ])
    gen = EventProximitySignalGen(calendar=cal, universe=["SPY"], window_days=5)
    assert gen.generate(dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc)) == []
```

- [ ] **Step 2: Run the test, watch it fail**

```bash
uv run pytest tests/test_signals_event_proximity.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement the generator**

Create `src/trading_assistant/signals/event_proximity.py`:

```python
"""Event-proximity signal generator: upcoming FOMC/CPI/NFP/earnings."""

from __future__ import annotations

import datetime as dt
import hashlib

from trading_assistant.calendars.events import EventCalendar
from trading_assistant.signals.model import Signal, SignalKind


class EventProximitySignalGen:
    name = "event_proximity"

    def __init__(self, calendar: EventCalendar, universe: list[str], window_days: int = 5) -> None:
        self._cal = calendar
        self._universe = [u.upper() for u in universe]
        self._window = window_days

    def generate(self, now: dt.datetime) -> list[Signal]:
        today = now.date()
        end = today + dt.timedelta(days=self._window)
        events = self._cal.events_in_window(today, end)
        out: list[Signal] = []
        for ev in events:
            days_until = (ev.date - today).days
            for symbol in sorted(ev.symbols & set(self._universe)):
                key = f"evt:{symbol}:{ev.kind.value}:{ev.date.isoformat()}"
                sid = "evt_" + hashlib.sha256(key.encode()).hexdigest()[:16]
                out.append(
                    Signal(
                        id=sid,
                        kind=SignalKind.EVENT_PROXIMITY,
                        symbol=symbol,
                        created_at=now,
                        strength=0.6,
                        evidence={
                            "event_kind": ev.kind.value,
                            "event_date": ev.date.isoformat(),
                            "days_until": days_until,
                        },
                    )
                )
        return out
```

- [ ] **Step 4: Run the test, watch it pass**

```bash
uv run pytest tests/test_signals_event_proximity.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/trading_assistant/signals/event_proximity.py \
        tests/test_signals_event_proximity.py
git commit -m "feat(signals): add EventProximitySignalGen for upcoming macro events"
```

---

## Task 9: `TradeIntent` model + `TradeIntentRepo`

**Files:**
- Create: `src/trading_assistant/intents/__init__.py` (empty)
- Create: `src/trading_assistant/intents/model.py`
- Create: `src/trading_assistant/intents/repo.py`
- Create: `tests/test_intents_model.py`
- Create: `tests/test_intents_repo.py`

A `TradeIntent` is what the synthesizer produces: a structured options strategy with one or more legs, a rationale, and the signals that justified it. For Phase 2 we support these strategies (all suitable for beginning swing traders):

- `LONG_CALL` — one bought call, capped risk = premium paid, unlimited upside
- `LONG_PUT` — one bought put, capped risk = premium paid
- `BULL_CALL_SPREAD` — buy a near-the-money call, sell a higher-strike call; defined risk + defined reward
- `BEAR_PUT_SPREAD` — buy a near-the-money put, sell a lower-strike put; defined risk + defined reward

(Spreads are gentler on premium cost and avoid the "I bought a call and IV crushed" beginner trap. We'll let the LLM choose among these four.)

- [ ] **Step 1: Write the failing model test**

`tests/test_intents_model.py`:

```python
"""TradeIntent model tests."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from trading_assistant.intents.model import Leg, Strategy, TradeIntent


def _leg(strike: float, side: str = "buy", right: str = "C") -> Leg:
    return Leg(side=side, right=right, strike=strike, expiry=dt.date(2026, 6, 19), qty=1)


def test_long_call_must_have_exactly_one_buy_call_leg():
    intent = TradeIntent(
        id="i1",
        created_at=dt.datetime.now(dt.timezone.utc),
        signal_ids=["s1"],
        symbol="SPY",
        strategy=Strategy.LONG_CALL,
        legs=[_leg(740.0)],
        rationale_md="QQQ broke 20d high",
        max_loss_usd=250.0,
        max_gain_usd=None,
        confidence=0.6,
    )
    assert intent.strategy == Strategy.LONG_CALL


def test_bull_call_spread_must_have_two_legs_long_lower_short_higher():
    intent = TradeIntent(
        id="i2",
        created_at=dt.datetime.now(dt.timezone.utc),
        signal_ids=["s1"],
        symbol="SPY",
        strategy=Strategy.BULL_CALL_SPREAD,
        legs=[_leg(740.0, side="buy"), _leg(745.0, side="sell")],
        rationale_md="long-call-spread thesis",
        max_loss_usd=150.0,
        max_gain_usd=350.0,
        confidence=0.65,
    )
    assert len(intent.legs) == 2


def test_bull_call_spread_rejects_wrong_leg_order():
    with pytest.raises(ValidationError):
        TradeIntent(
            id="i3",
            created_at=dt.datetime.now(dt.timezone.utc),
            signal_ids=["s1"],
            symbol="SPY",
            strategy=Strategy.BULL_CALL_SPREAD,
            legs=[_leg(745.0, side="buy"), _leg(740.0, side="sell")],  # inverted
            rationale_md="x",
            max_loss_usd=100.0,
            max_gain_usd=200.0,
            confidence=0.5,
        )


def test_confidence_must_be_zero_to_one():
    with pytest.raises(ValidationError):
        TradeIntent(
            id="i4",
            created_at=dt.datetime.now(dt.timezone.utc),
            signal_ids=["s1"],
            symbol="SPY",
            strategy=Strategy.LONG_CALL,
            legs=[_leg(740.0)],
            rationale_md="x",
            max_loss_usd=100.0,
            max_gain_usd=None,
            confidence=1.5,
        )
```

- [ ] **Step 2: Run the test, watch it fail**

```bash
uv run pytest tests/test_intents_model.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement the model**

Create `src/trading_assistant/intents/__init__.py` (empty file).

Create `src/trading_assistant/intents/model.py`:

```python
"""TradeIntent: structured options trade idea produced by the synthesizer."""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Strategy(str, Enum):
    LONG_CALL = "long_call"
    LONG_PUT = "long_put"
    BULL_CALL_SPREAD = "bull_call_spread"
    BEAR_PUT_SPREAD = "bear_put_spread"


class Leg(BaseModel):
    side: Literal["buy", "sell"]
    right: Literal["C", "P"]
    strike: float
    expiry: dt.date
    qty: int = Field(ge=1)


class TradeIntent(BaseModel):
    id: str
    created_at: dt.datetime
    signal_ids: list[str]
    symbol: str
    strategy: Strategy
    legs: list[Leg]
    rationale_md: str
    max_loss_usd: float = Field(ge=0)
    max_gain_usd: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("symbol")
    @classmethod
    def _upper_symbol(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def _check_strategy_shape(self) -> "TradeIntent":
        s = self.strategy
        legs = self.legs
        if s == Strategy.LONG_CALL:
            if not (len(legs) == 1 and legs[0].side == "buy" and legs[0].right == "C"):
                raise ValueError("long_call must be exactly one buy-call leg")
        elif s == Strategy.LONG_PUT:
            if not (len(legs) == 1 and legs[0].side == "buy" and legs[0].right == "P"):
                raise ValueError("long_put must be exactly one buy-put leg")
        elif s == Strategy.BULL_CALL_SPREAD:
            if len(legs) != 2:
                raise ValueError("bull_call_spread needs exactly two legs")
            long_leg = next((l for l in legs if l.side == "buy" and l.right == "C"), None)
            short_leg = next((l for l in legs if l.side == "sell" and l.right == "C"), None)
            if long_leg is None or short_leg is None:
                raise ValueError("bull_call_spread needs one buy-call and one sell-call")
            if long_leg.strike >= short_leg.strike:
                raise ValueError("bull_call_spread: long strike must be below short strike")
        elif s == Strategy.BEAR_PUT_SPREAD:
            if len(legs) != 2:
                raise ValueError("bear_put_spread needs exactly two legs")
            long_leg = next((l for l in legs if l.side == "buy" and l.right == "P"), None)
            short_leg = next((l for l in legs if l.side == "sell" and l.right == "P"), None)
            if long_leg is None or short_leg is None:
                raise ValueError("bear_put_spread needs one buy-put and one sell-put")
            if long_leg.strike <= short_leg.strike:
                raise ValueError("bear_put_spread: long strike must be above short strike")
        return self
```

- [ ] **Step 4: Run the model test, watch it pass**

```bash
uv run pytest tests/test_intents_model.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Write the failing repo test**

`tests/test_intents_repo.py`:

```python
"""TradeIntentRepo tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.db.schema import create_schema
from trading_assistant.intents.model import Leg, Strategy, TradeIntent
from trading_assistant.intents.repo import TradeIntentRepo
from trading_assistant.signals.model import Signal, SignalKind
from trading_assistant.signals.repo import SignalRepo


def _make_intent(intent_id: str, signal_id: str, status: str = "validated") -> TradeIntent:
    return TradeIntent(
        id=intent_id,
        created_at=dt.datetime(2026, 5, 11, 14, tzinfo=dt.timezone.utc),
        signal_ids=[signal_id],
        symbol="SPY",
        strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=740.0, expiry=dt.date(2026, 6, 19), qty=1)],
        rationale_md="test thesis",
        max_loss_usd=200.0,
        max_gain_usd=None,
        confidence=0.6,
    )


def _persist_signal(conn, sid: str) -> None:
    repo = SignalRepo(conn)
    repo.write(Signal(
        id=sid,
        kind=SignalKind.NEWS_CATALYST,
        symbol="SPY",
        created_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
        strength=0.5,
        evidence={},
    ))


def test_write_validated_intent_round_trip(db_conn):
    create_schema(db_conn)
    _persist_signal(db_conn, "sig1")
    repo = TradeIntentRepo(db_conn)
    intent = _make_intent("i1", "sig1")
    repo.write(intent, status="validated", rejection_reason=None)
    fetched = repo.list_since(intent.created_at - dt.timedelta(minutes=1))
    assert len(fetched) == 1
    row = fetched[0]
    assert row.intent == intent
    assert row.status == "validated"
    assert row.rejection_reason is None


def test_write_rejected_intent_records_reason(db_conn):
    create_schema(db_conn)
    _persist_signal(db_conn, "sig2")
    repo = TradeIntentRepo(db_conn)
    intent = _make_intent("i2", "sig2")
    repo.write(intent, status="rejected", rejection_reason="spread_too_wide")
    fetched = repo.list_since(intent.created_at - dt.timedelta(minutes=1))
    assert fetched[0].rejection_reason == "spread_too_wide"
```

- [ ] **Step 6: Run repo test, watch it fail**

```bash
uv run pytest tests/test_intents_repo.py -v
```

Expected: ImportError.

- [ ] **Step 7: Implement the repo**

Create `src/trading_assistant/intents/repo.py`:

```python
"""Persistence for TradeIntent rows."""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from dataclasses import dataclass

from trading_assistant.intents.model import Leg, Strategy, TradeIntent


@dataclass(frozen=True)
class TradeIntentRow:
    intent: TradeIntent
    status: str
    rejection_reason: str | None


class TradeIntentRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def write(self, intent: TradeIntent, status: str, rejection_reason: str | None) -> None:
        # The signals table requires signal_id to exist; for multi-signal intents
        # we record the first signal_id and store the full list inside structure_json.
        primary_signal_id = intent.signal_ids[0]
        structure = {
            "strategy": intent.strategy.value,
            "legs": [leg.model_dump(mode="json") for leg in intent.legs],
            "max_loss_usd": intent.max_loss_usd,
            "max_gain_usd": intent.max_gain_usd,
            "confidence": intent.confidence,
            "signal_ids": intent.signal_ids,
        }
        self._conn.execute(
            """
            INSERT OR REPLACE INTO trade_intents
                (id, created_at, signal_id, symbol, structure_json, rationale_md,
                 user_thesis, status, rejection_reason)
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                intent.id,
                intent.created_at.isoformat(),
                primary_signal_id,
                intent.symbol,
                json.dumps(structure),
                intent.rationale_md,
                status,
                rejection_reason,
            ),
        )
        self._conn.commit()

    def list_since(self, cutoff: dt.datetime) -> list[TradeIntentRow]:
        rows = self._conn.execute(
            """
            SELECT id, created_at, signal_id, symbol, structure_json, rationale_md,
                   status, rejection_reason
            FROM trade_intents
            WHERE created_at >= ?
            ORDER BY created_at ASC
            """,
            (cutoff.isoformat(),),
        ).fetchall()
        out: list[TradeIntentRow] = []
        for r in rows:
            struct = json.loads(r["structure_json"])
            intent = TradeIntent(
                id=r["id"],
                created_at=dt.datetime.fromisoformat(r["created_at"]),
                signal_ids=struct["signal_ids"],
                symbol=r["symbol"],
                strategy=Strategy(struct["strategy"]),
                legs=[Leg(**leg) for leg in struct["legs"]],
                rationale_md=r["rationale_md"],
                max_loss_usd=struct["max_loss_usd"],
                max_gain_usd=struct["max_gain_usd"],
                confidence=struct["confidence"],
            )
            out.append(TradeIntentRow(intent=intent, status=r["status"],
                                       rejection_reason=r["rejection_reason"]))
        return out
```

- [ ] **Step 8: Run repo test, watch it pass**

```bash
uv run pytest tests/test_intents_repo.py -v
```

Expected: 2 passed.

- [ ] **Step 9: Commit**

```bash
git add src/trading_assistant/intents/__init__.py \
        src/trading_assistant/intents/model.py \
        src/trading_assistant/intents/repo.py \
        tests/test_intents_model.py tests/test_intents_repo.py
git commit -m "feat(intents): add TradeIntent model and TradeIntentRepo"
```

---

## Task 10: `AnthropicClient` — thin Claude wrapper

**Files:**
- Create: `src/trading_assistant/brain/__init__.py` (empty)
- Create: `src/trading_assistant/brain/anthropic_client.py`
- Create: `tests/test_brain_anthropic_client.py`

A thin Protocol-friendly wrapper around the Anthropic SDK that:
- Takes a system prompt + user message
- Enforces a hard `max_tokens` cap (default 2000)
- Logs request/response/token usage via structlog
- Tags the static portion of the system prompt for prompt caching
- Raises a typed error on failure (no naked SDK exceptions leaking)

We don't call the real API in unit tests — we inject a fake client.

- [ ] **Step 1: Write the failing test**

`tests/test_brain_anthropic_client.py`:

```python
"""AnthropicClient tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from trading_assistant.brain.anthropic_client import (
    AnthropicClient,
    AnthropicError,
    LLMResponse,
)


@dataclass
class _FakeUsage:
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class _FakeContent:
    text: str


@dataclass
class _FakeResp:
    content: list[_FakeContent]
    usage: _FakeUsage


class _FakeSDK:
    def __init__(self, response: _FakeResp | None = None, raise_exc: Exception | None = None) -> None:
        self._response = response
        self._raise = raise_exc
        self.last_kwargs: dict | None = None

    class _Messages:
        def __init__(self, parent: "_FakeSDK") -> None:
            self._parent = parent

        def create(self, **kwargs):  # noqa: ANN003
            self._parent.last_kwargs = kwargs
            if self._parent._raise:
                raise self._parent._raise
            return self._parent._response

    @property
    def messages(self) -> "_FakeSDK._Messages":
        return _FakeSDK._Messages(self)


def test_complete_returns_text_and_usage():
    fake = _FakeSDK(_FakeResp(
        content=[_FakeContent("hello world")],
        usage=_FakeUsage(input_tokens=100, output_tokens=20),
    ))
    client = AnthropicClient(sdk=fake, model="claude-opus-4-7", max_tokens=500)
    resp = client.complete(system="static-system", user="user msg")
    assert isinstance(resp, LLMResponse)
    assert resp.text == "hello world"
    assert resp.input_tokens == 100
    assert resp.output_tokens == 20


def test_complete_enforces_max_tokens_in_call():
    fake = _FakeSDK(_FakeResp(content=[_FakeContent("ok")], usage=_FakeUsage(1, 1)))
    client = AnthropicClient(sdk=fake, model="claude-opus-4-7", max_tokens=777)
    client.complete(system="s", user="u")
    assert fake.last_kwargs["max_tokens"] == 777


def test_complete_uses_cache_control_on_system_prompt():
    fake = _FakeSDK(_FakeResp(content=[_FakeContent("ok")], usage=_FakeUsage(1, 1)))
    client = AnthropicClient(sdk=fake, model="claude-opus-4-7", max_tokens=500)
    client.complete(system="static system text", user="user")
    system_block = fake.last_kwargs["system"]
    assert isinstance(system_block, list)
    assert system_block[0]["cache_control"] == {"type": "ephemeral"}


def test_complete_wraps_sdk_exception():
    fake = _FakeSDK(raise_exc=RuntimeError("boom"))
    client = AnthropicClient(sdk=fake, model="claude-opus-4-7", max_tokens=500)
    with pytest.raises(AnthropicError):
        client.complete(system="s", user="u")
```

- [ ] **Step 2: Run the test, watch it fail**

```bash
uv run pytest tests/test_brain_anthropic_client.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement the client**

Create `src/trading_assistant/brain/__init__.py` (empty).

Create `src/trading_assistant/brain/anthropic_client.py`:

```python
"""Thin wrapper around the Anthropic SDK for the trade-idea synthesizer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import structlog

log = structlog.get_logger(__name__)


class AnthropicError(Exception):
    """Raised when the LLM call fails for any reason we care about."""


@dataclass(frozen=True)
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int


class _AnthropicSDK(Protocol):
    """Structural subset of the Anthropic SDK we depend on."""

    messages: Any  # SDK exposes `.messages.create(...)`


class AnthropicClient:
    def __init__(self, sdk: _AnthropicSDK, model: str, max_tokens: int = 2000) -> None:
        self._sdk = sdk
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, system: str, user: str) -> LLMResponse:
        system_block = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        try:
            resp = self._sdk.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_block,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # noqa: BLE001 — intentional broad wrap
            log.warning("anthropic_call_failed", error=str(exc))
            raise AnthropicError(str(exc)) from exc

        text = "".join(getattr(block, "text", "") for block in resp.content)
        u = resp.usage
        out = LLMResponse(
            text=text,
            input_tokens=getattr(u, "input_tokens", 0),
            output_tokens=getattr(u, "output_tokens", 0),
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0),
            cache_creation_tokens=getattr(u, "cache_creation_input_tokens", 0),
        )
        log.info(
            "anthropic_call_ok",
            model=self._model,
            input_tokens=out.input_tokens,
            output_tokens=out.output_tokens,
            cache_read_tokens=out.cache_read_tokens,
            cache_creation_tokens=out.cache_creation_tokens,
        )
        return out
```

- [ ] **Step 4: Run the test, watch it pass**

```bash
uv run pytest tests/test_brain_anthropic_client.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/trading_assistant/brain/__init__.py \
        src/trading_assistant/brain/anthropic_client.py \
        tests/test_brain_anthropic_client.py
git commit -m "feat(brain): add AnthropicClient with prompt caching and token cap"
```

---

## Task 11: `IdeaSynthesizer` — call Claude, parse structured intents

**Files:**
- Create: `src/trading_assistant/brain/synthesizer.py`
- Create: `tests/test_brain_synthesizer.py`

The synthesizer takes a list of active `Signal`s plus a market snapshot (quotes) plus recent news titles, builds a JSON-output-constrained prompt, calls Claude through `AnthropicClient`, and parses the response into `TradeIntent` candidates. It does **not** validate them — that's the validator's job.

The prompt instructs Claude to:
- Output strict JSON: `{"proposals": [...]}`
- Every proposal must reference at least one signal_id from the input
- Choose strategy from `{long_call, long_put, bull_call_spread, bear_put_spread}` only
- Stay within the configured universe
- Set realistic `max_loss_usd` and `confidence`
- Return an empty `proposals` list when no setup is compelling

- [ ] **Step 1: Write the failing test**

`tests/test_brain_synthesizer.py`:

```python
"""IdeaSynthesizer tests."""

from __future__ import annotations

import datetime as dt
import json

from trading_assistant.brain.anthropic_client import LLMResponse
from trading_assistant.brain.synthesizer import IdeaSynthesizer
from trading_assistant.ingest.market_data import Quote
from trading_assistant.intents.model import Strategy
from trading_assistant.signals.model import Signal, SignalKind


class _FakeLLM:
    def __init__(self, text: str) -> None:
        self._text = text
        self.last_user: str | None = None

    def complete(self, system: str, user: str) -> LLMResponse:
        self.last_user = user
        return LLMResponse(
            text=self._text,
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=0,
            cache_creation_tokens=0,
        )


def _sig(symbol: str = "SPY") -> Signal:
    return Signal(
        id="sig_1",
        kind=SignalKind.TECHNICAL_BREAKOUT,
        symbol=symbol,
        created_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
        strength=0.7,
        evidence={"direction": "up", "close": 739.0, "20d_high": 735.0},
    )


def _quote(symbol: str = "SPY", mid: float = 739.0) -> Quote:
    return Quote(symbol=symbol, bid=mid - 0.05, ask=mid + 0.05, last=mid,
                 ts=dt.datetime.now(dt.timezone.utc), source="fake")


def test_synthesizer_parses_long_call_proposal():
    payload = {
        "proposals": [
            {
                "symbol": "SPY",
                "strategy": "long_call",
                "legs": [{"side": "buy", "right": "C", "strike": 745.0,
                           "expiry": "2026-06-19", "qty": 1}],
                "rationale_md": "Breakout above 20d high.",
                "max_loss_usd": 250.0,
                "max_gain_usd": None,
                "confidence": 0.6,
                "signal_ids": ["sig_1"],
            }
        ]
    }
    llm = _FakeLLM(json.dumps(payload))
    synth = IdeaSynthesizer(llm=llm, universe=["SPY"])
    intents = synth.synthesize(
        signals=[_sig()],
        quotes={"SPY": _quote()},
        recent_news=[{"title": "SPY pushes higher", "source": "test"}],
        now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
    )
    assert len(intents) == 1
    assert intents[0].strategy == Strategy.LONG_CALL
    assert intents[0].signal_ids == ["sig_1"]


def test_synthesizer_returns_empty_when_llm_returns_empty_proposals():
    llm = _FakeLLM('{"proposals": []}')
    synth = IdeaSynthesizer(llm=llm, universe=["SPY"])
    out = synth.synthesize(
        signals=[_sig()],
        quotes={"SPY": _quote()},
        recent_news=[],
        now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
    )
    assert out == []


def test_synthesizer_drops_proposals_referencing_unknown_signal_ids():
    payload = {
        "proposals": [
            {
                "symbol": "SPY", "strategy": "long_call",
                "legs": [{"side": "buy", "right": "C", "strike": 745.0,
                           "expiry": "2026-06-19", "qty": 1}],
                "rationale_md": "x", "max_loss_usd": 100.0, "max_gain_usd": None,
                "confidence": 0.5, "signal_ids": ["does_not_exist"],
            }
        ]
    }
    synth = IdeaSynthesizer(llm=_FakeLLM(json.dumps(payload)), universe=["SPY"])
    out = synth.synthesize(
        signals=[_sig()],
        quotes={"SPY": _quote()},
        recent_news=[],
        now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
    )
    assert out == []


def test_synthesizer_drops_proposals_outside_universe():
    payload = {
        "proposals": [
            {
                "symbol": "AAPL", "strategy": "long_call",
                "legs": [{"side": "buy", "right": "C", "strike": 200.0,
                           "expiry": "2026-06-19", "qty": 1}],
                "rationale_md": "x", "max_loss_usd": 100.0, "max_gain_usd": None,
                "confidence": 0.5, "signal_ids": ["sig_1"],
            }
        ]
    }
    synth = IdeaSynthesizer(llm=_FakeLLM(json.dumps(payload)), universe=["SPY"])
    out = synth.synthesize(
        signals=[_sig()],
        quotes={"SPY": _quote()},
        recent_news=[],
        now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
    )
    assert out == []


def test_synthesizer_recovers_from_text_around_json():
    payload = {
        "proposals": [
            {"symbol": "SPY", "strategy": "long_call",
             "legs": [{"side": "buy", "right": "C", "strike": 745.0,
                        "expiry": "2026-06-19", "qty": 1}],
             "rationale_md": "x", "max_loss_usd": 100.0, "max_gain_usd": None,
             "confidence": 0.5, "signal_ids": ["sig_1"]}
        ]
    }
    wrapped = f"Sure, here you go:\n```json\n{json.dumps(payload)}\n```\nDone."
    synth = IdeaSynthesizer(llm=_FakeLLM(wrapped), universe=["SPY"])
    out = synth.synthesize(
        signals=[_sig()],
        quotes={"SPY": _quote()},
        recent_news=[],
        now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
    )
    assert len(out) == 1


def test_synthesizer_returns_empty_on_unparseable_response():
    synth = IdeaSynthesizer(llm=_FakeLLM("not json at all"), universe=["SPY"])
    out = synth.synthesize(
        signals=[_sig()],
        quotes={"SPY": _quote()},
        recent_news=[],
        now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
    )
    assert out == []
```

- [ ] **Step 2: Run the test, watch it fail**

```bash
uv run pytest tests/test_brain_synthesizer.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement the synthesizer**

Create `src/trading_assistant/brain/synthesizer.py`:

```python
"""IdeaSynthesizer: turn signals + market state into structured TradeIntents via Claude."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from typing import Any, Protocol

import structlog
from pydantic import ValidationError

from trading_assistant.brain.anthropic_client import LLMResponse
from trading_assistant.ingest.market_data import Quote
from trading_assistant.intents.model import Leg, Strategy, TradeIntent
from trading_assistant.signals.model import Signal

log = structlog.get_logger(__name__)


_SYSTEM_PROMPT = """\
You are an options-trading idea generator for a beginner using a paper-money account.
Universe: {universe}.
Allowed strategies: long_call, long_put, bull_call_spread, bear_put_spread.
Constraints:
- Every proposal MUST cite at least one signal_id from the input.
- Strikes must be plausible relative to the current mid quote.
- Expiry: 14–45 calendar days out for swing positioning.
- max_loss_usd reflects total risk per contract (premium paid for long, max spread loss for spreads).
- confidence in [0.0, 1.0]. Be conservative — 0.5 is "modestly compelling."
- Return STRICT JSON ONLY in the shape: {{"proposals": [...]}}. No prose, no markdown fences.
- Return {{"proposals": []}} when no setup is compelling.
"""


class _LLM(Protocol):
    def complete(self, system: str, user: str) -> LLMResponse: ...


class IdeaSynthesizer:
    def __init__(self, llm: _LLM, universe: list[str]) -> None:
        self._llm = llm
        self._universe = [u.upper() for u in universe]

    def synthesize(
        self,
        signals: list[Signal],
        quotes: dict[str, Quote],
        recent_news: list[dict[str, Any]],
        now: dt.datetime,
    ) -> list[TradeIntent]:
        if not signals:
            return []
        valid_signal_ids = {s.id for s in signals}
        system = _SYSTEM_PROMPT.format(universe=", ".join(self._universe))
        user = json.dumps({
            "now": now.isoformat(),
            "signals": [s.model_dump(mode="json") for s in signals],
            "quotes": {sym: {"bid": q.bid, "ask": q.ask, "mid": (q.bid + q.ask) / 2}
                       for sym, q in quotes.items()},
            "recent_news": recent_news[:20],
        }, default=str)

        try:
            resp = self._llm.complete(system=system, user=user)
        except Exception as exc:  # noqa: BLE001
            log.warning("synthesizer_llm_failed", error=str(exc))
            return []

        payload = _extract_json(resp.text)
        if payload is None:
            log.warning("synthesizer_unparseable_response", sample=resp.text[:200])
            return []

        out: list[TradeIntent] = []
        for prop in payload.get("proposals", []):
            intent = self._build_intent(prop, valid_signal_ids, now)
            if intent is not None:
                out.append(intent)
        return out

    def _build_intent(
        self, prop: dict, valid_signal_ids: set[str], now: dt.datetime,
    ) -> TradeIntent | None:
        try:
            symbol = prop["symbol"].upper()
            if symbol not in self._universe:
                return None
            signal_ids = list(prop.get("signal_ids") or [])
            if not signal_ids or not set(signal_ids).issubset(valid_signal_ids):
                return None
            legs = [Leg(**leg) for leg in prop["legs"]]
            sig_hash = hashlib.sha256("|".join(sorted(signal_ids)).encode()).hexdigest()[:16]
            intent_id = f"intent_{sig_hash}_{prop['strategy']}"
            return TradeIntent(
                id=intent_id,
                created_at=now,
                signal_ids=signal_ids,
                symbol=symbol,
                strategy=Strategy(prop["strategy"]),
                legs=legs,
                rationale_md=prop["rationale_md"],
                max_loss_usd=float(prop["max_loss_usd"]),
                max_gain_usd=(float(prop["max_gain_usd"]) if prop.get("max_gain_usd") is not None else None),
                confidence=float(prop["confidence"]),
            )
        except (KeyError, ValueError, ValidationError) as exc:
            log.warning("synthesizer_proposal_invalid", error=str(exc), proposal=prop)
            return None


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _extract_json(text: str) -> dict | None:
    """Tolerate Claude wrapping JSON in ```json ... ``` or adding prose around it."""
    # First try: whole string is JSON.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Second try: extract from a ```json ... ``` fence.
    m = _FENCE_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Third try: first balanced `{...}` block.
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None
```

- [ ] **Step 4: Run the test, watch it pass**

```bash
uv run pytest tests/test_brain_synthesizer.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/trading_assistant/brain/synthesizer.py tests/test_brain_synthesizer.py
git commit -m "feat(brain): add IdeaSynthesizer with strict JSON parsing and signal-id validation"
```

---

## Task 12: `Validator` core + `GuardResult`

**Files:**
- Create: `src/trading_assistant/brain/validator.py`
- Create: `tests/test_brain_validator.py`

The validator runs a candidate intent through a chain of guards. Each guard returns either `accept` or `reject(reason)`. The first reject short-circuits; subsequent guards are not run. Every result is logged.

- [ ] **Step 1: Write the failing test**

`tests/test_brain_validator.py`:

```python
"""Validator + guard chain tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.validator import (
    GuardOutcome,
    GuardResult,
    Validator,
)
from trading_assistant.intents.model import Leg, Strategy, TradeIntent


def _intent() -> TradeIntent:
    return TradeIntent(
        id="i1",
        created_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
        signal_ids=["sig"],
        symbol="SPY",
        strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=740.0,
                   expiry=dt.date(2026, 6, 19), qty=1)],
        rationale_md="x",
        max_loss_usd=200.0,
        max_gain_usd=None,
        confidence=0.5,
    )


class _Always:
    name = "always"

    def __init__(self, outcome: GuardResult) -> None:
        self._out = outcome
        self.called = False

    def check(self, intent: TradeIntent) -> GuardResult:
        self.called = True
        return self._out


def test_accepts_when_all_guards_pass():
    g1 = _Always(GuardResult(outcome=GuardOutcome.ACCEPT, reason=None))
    g2 = _Always(GuardResult(outcome=GuardOutcome.ACCEPT, reason=None))
    v = Validator(guards=[g1, g2])
    decision = v.validate(_intent())
    assert decision.outcome == GuardOutcome.ACCEPT
    assert decision.reason is None
    assert g1.called and g2.called


def test_short_circuits_on_first_reject():
    g1 = _Always(GuardResult(outcome=GuardOutcome.REJECT, reason="spread_too_wide"))
    g2 = _Always(GuardResult(outcome=GuardOutcome.ACCEPT, reason=None))
    v = Validator(guards=[g1, g2])
    decision = v.validate(_intent())
    assert decision.outcome == GuardOutcome.REJECT
    assert decision.reason == "spread_too_wide"
    assert g1.called
    assert not g2.called


def test_no_guards_means_accept():
    v = Validator(guards=[])
    decision = v.validate(_intent())
    assert decision.outcome == GuardOutcome.ACCEPT
```

- [ ] **Step 2: Run the test, watch it fail**

```bash
uv run pytest tests/test_brain_validator.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement the validator**

Create `src/trading_assistant/brain/validator.py`:

```python
"""Validator: run a candidate TradeIntent through a chain of guards."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import structlog

from trading_assistant.intents.model import TradeIntent

log = structlog.get_logger(__name__)


class GuardOutcome(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"


@dataclass(frozen=True)
class GuardResult:
    outcome: GuardOutcome
    reason: str | None


class Guard(Protocol):
    name: str

    def check(self, intent: TradeIntent) -> GuardResult: ...


class Validator:
    def __init__(self, guards: list[Guard]) -> None:
        self._guards = guards

    def validate(self, intent: TradeIntent) -> GuardResult:
        for guard in self._guards:
            result = guard.check(intent)
            if result.outcome == GuardOutcome.REJECT:
                log.info("intent_rejected", intent_id=intent.id, guard=guard.name,
                         reason=result.reason)
                return result
        log.info("intent_accepted", intent_id=intent.id)
        return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)
```

- [ ] **Step 4: Run the test, watch it pass**

```bash
uv run pytest tests/test_brain_validator.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/trading_assistant/brain/validator.py tests/test_brain_validator.py
git commit -m "feat(brain): add Validator with short-circuit guard chain"
```

---

## Task 13: Guards — spread filter + pin-risk

**Files:**
- Create: `src/trading_assistant/brain/guards/__init__.py` (empty)
- Create: `src/trading_assistant/brain/guards/spread.py`
- Create: `src/trading_assistant/brain/guards/pin_risk.py`
- Create: `tests/test_guards_spread.py`
- Create: `tests/test_guards_pin_risk.py`

**Spread guard (`spread.py`)**: Looks up the actual chain quotes for each leg. Rejects if any leg has `(ask − bid) / mid > max_spread_pct_of_mid`. Wide spreads = paper-trade fills that look great but real fills that will hurt.

**Pin-risk guard (`pin_risk.py`)**: For any short leg with ≤7 days to expiry, rejects if the underlying mid is within `pin_risk_pct` of the strike. "Pin risk" is the danger of being assigned (or not) right at expiry when the underlying closes very close to your strike — assignment behavior is unpredictable. We avoid the whole region.

- [ ] **Step 1: Write the failing spread-guard test**

`tests/test_guards_spread.py`:

```python
"""SpreadGuard tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.guards.spread import SpreadGuard
from trading_assistant.brain.validator import GuardOutcome
from trading_assistant.ingest.options_chain import OptionContract
from trading_assistant.intents.model import Leg, Strategy, TradeIntent


class _FakeChains:
    def __init__(self, by_symbol: dict[str, list[OptionContract]]) -> None:
        self._chains = by_symbol

    def chain(self, symbol: str) -> list[OptionContract]:
        return self._chains.get(symbol, [])


def _intent(strike: float = 740.0) -> TradeIntent:
    return TradeIntent(
        id="i", created_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
        signal_ids=["s"], symbol="SPY", strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=strike,
                   expiry=dt.date(2026, 6, 19), qty=1)],
        rationale_md="x", max_loss_usd=200.0, max_gain_usd=None, confidence=0.5,
    )


def _contract(strike: float, bid: float, ask: float) -> OptionContract:
    return OptionContract(
        occ_symbol=f"X{strike}", underlying="SPY",
        expiry=dt.date(2026, 6, 19), strike=strike, right="C",
        bid=bid, ask=ask, last=(bid + ask) / 2, iv=0.20,
    )


def test_accepts_when_spread_within_threshold():
    chains = _FakeChains({"SPY": [_contract(740.0, bid=4.00, ask=4.10)]})
    guard = SpreadGuard(chain_client=chains, max_pct=0.05)
    assert guard.check(_intent()).outcome == GuardOutcome.ACCEPT


def test_rejects_when_spread_too_wide():
    chains = _FakeChains({"SPY": [_contract(740.0, bid=4.00, ask=5.00)]})
    guard = SpreadGuard(chain_client=chains, max_pct=0.05)
    res = guard.check(_intent())
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "spread_too_wide"


def test_rejects_when_leg_not_in_chain():
    chains = _FakeChains({"SPY": []})
    guard = SpreadGuard(chain_client=chains, max_pct=0.05)
    res = guard.check(_intent())
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "leg_quote_missing"


def test_rejects_when_bid_or_ask_is_zero():
    chains = _FakeChains({"SPY": [_contract(740.0, bid=0.0, ask=4.10)]})
    guard = SpreadGuard(chain_client=chains, max_pct=0.05)
    res = guard.check(_intent())
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "leg_quote_missing"
```

- [ ] **Step 2: Run spread test, watch it fail**

```bash
uv run pytest tests/test_guards_spread.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `SpreadGuard`**

Create `src/trading_assistant/brain/guards/__init__.py` (empty).

Create `src/trading_assistant/brain/guards/spread.py`:

```python
"""SpreadGuard: reject intents where any leg has too-wide bid-ask spread."""

from __future__ import annotations

from typing import Protocol

from trading_assistant.brain.validator import GuardOutcome, GuardResult
from trading_assistant.ingest.options_chain import OptionContract
from trading_assistant.intents.model import TradeIntent


class _ChainClient(Protocol):
    def chain(self, symbol: str) -> list[OptionContract]: ...


class SpreadGuard:
    name = "spread"

    def __init__(self, chain_client: _ChainClient, max_pct: float) -> None:
        self._chain = chain_client
        self._max = max_pct

    def check(self, intent: TradeIntent) -> GuardResult:
        chain = self._chain.chain(intent.symbol)
        for leg in intent.legs:
            match = self._find(chain, leg.strike, leg.expiry, leg.right)
            if match is None or match.bid <= 0 or match.ask <= 0:
                return GuardResult(outcome=GuardOutcome.REJECT,
                                   reason="leg_quote_missing")
            mid = (match.bid + match.ask) / 2.0
            if mid <= 0:
                return GuardResult(outcome=GuardOutcome.REJECT,
                                   reason="leg_quote_missing")
            spread_pct = (match.ask - match.bid) / mid
            if spread_pct > self._max:
                return GuardResult(outcome=GuardOutcome.REJECT,
                                   reason="spread_too_wide")
        return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)

    @staticmethod
    def _find(chain: list[OptionContract], strike: float, expiry, right: str) -> OptionContract | None:
        for c in chain:
            if c.strike == strike and c.expiry == expiry and c.right == right:
                return c
        return None
```

- [ ] **Step 4: Run spread test, watch it pass**

```bash
uv run pytest tests/test_guards_spread.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Write the failing pin-risk test**

`tests/test_guards_pin_risk.py`:

```python
"""PinRiskGuard tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.guards.pin_risk import PinRiskGuard
from trading_assistant.brain.validator import GuardOutcome
from trading_assistant.ingest.market_data import Quote
from trading_assistant.intents.model import Leg, Strategy, TradeIntent


class _FakeQuotes:
    def __init__(self, mids: dict[str, float]) -> None:
        self._mids = mids

    def snapshot(self, symbols: list[str]) -> dict[str, Quote]:
        return {s: Quote(symbol=s, bid=self._mids[s] - 0.05, ask=self._mids[s] + 0.05,
                          last=self._mids[s], ts=dt.datetime.now(dt.timezone.utc),
                          source="fake")
                for s in symbols if s in self._mids}


def _spread_intent(strike_long: float, strike_short: float, days_to_exp: int) -> TradeIntent:
    expiry = dt.date(2026, 5, 11) + dt.timedelta(days=days_to_exp)
    return TradeIntent(
        id="i", created_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
        signal_ids=["s"], symbol="SPY", strategy=Strategy.BULL_CALL_SPREAD,
        legs=[
            Leg(side="buy", right="C", strike=strike_long, expiry=expiry, qty=1),
            Leg(side="sell", right="C", strike=strike_short, expiry=expiry, qty=1),
        ],
        rationale_md="x", max_loss_usd=100.0, max_gain_usd=200.0, confidence=0.5,
    )


def test_accepts_when_expiry_outside_7_day_window():
    guard = PinRiskGuard(quote_client=_FakeQuotes({"SPY": 740.0}),
                          pin_pct=0.015, now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    intent = _spread_intent(strike_long=740.0, strike_short=740.5, days_to_exp=14)
    assert guard.check(intent).outcome == GuardOutcome.ACCEPT


def test_rejects_when_short_strike_within_pin_band_at_expiry_under_7_days():
    guard = PinRiskGuard(quote_client=_FakeQuotes({"SPY": 740.0}),
                          pin_pct=0.015, now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    # 740 mid, 1.5% band = ±$11.10; short strike at 741 is within band.
    intent = _spread_intent(strike_long=738.0, strike_short=741.0, days_to_exp=5)
    res = guard.check(intent)
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "pin_risk"


def test_accepts_when_short_strike_outside_pin_band():
    guard = PinRiskGuard(quote_client=_FakeQuotes({"SPY": 740.0}),
                          pin_pct=0.015, now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    # 740 mid, 1.5% band = ±$11.10; short strike at 760 is outside band.
    intent = _spread_intent(strike_long=755.0, strike_short=760.0, days_to_exp=5)
    assert guard.check(intent).outcome == GuardOutcome.ACCEPT


def test_long_only_intent_has_no_pin_risk():
    """LONG_CALL has no short leg, so pin risk doesn't apply."""
    guard = PinRiskGuard(quote_client=_FakeQuotes({"SPY": 740.0}),
                          pin_pct=0.015, now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    intent = TradeIntent(
        id="i", created_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
        signal_ids=["s"], symbol="SPY", strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=740.0,
                   expiry=dt.date(2026, 5, 14), qty=1)],
        rationale_md="x", max_loss_usd=100.0, max_gain_usd=None, confidence=0.5,
    )
    assert guard.check(intent).outcome == GuardOutcome.ACCEPT
```

- [ ] **Step 6: Run pin-risk test, watch it fail**

```bash
uv run pytest tests/test_guards_pin_risk.py -v
```

Expected: ImportError.

- [ ] **Step 7: Implement `PinRiskGuard`**

Create `src/trading_assistant/brain/guards/pin_risk.py`:

```python
"""PinRiskGuard: reject if a short leg expires within 7d AND underlying is near strike."""

from __future__ import annotations

import datetime as dt
from typing import Protocol

from trading_assistant.brain.validator import GuardOutcome, GuardResult
from trading_assistant.ingest.market_data import Quote
from trading_assistant.intents.model import TradeIntent

_PIN_WINDOW_DAYS = 7


class _QuoteClient(Protocol):
    def snapshot(self, symbols: list[str]) -> dict[str, Quote]: ...


class PinRiskGuard:
    name = "pin_risk"

    def __init__(self, quote_client: _QuoteClient, pin_pct: float, now: dt.datetime) -> None:
        self._quote = quote_client
        self._pin = pin_pct
        self._now = now

    def check(self, intent: TradeIntent) -> GuardResult:
        short_legs = [l for l in intent.legs if l.side == "sell"]
        if not short_legs:
            return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)

        # Only care about legs expiring within the pin window.
        today = self._now.date()
        in_window = [l for l in short_legs
                      if (l.expiry - today).days <= _PIN_WINDOW_DAYS]
        if not in_window:
            return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)

        quotes = self._quote.snapshot([intent.symbol])
        q = quotes.get(intent.symbol)
        if q is None:
            return GuardResult(outcome=GuardOutcome.REJECT, reason="underlying_quote_missing")
        mid = (q.bid + q.ask) / 2.0
        band = mid * self._pin
        for leg in in_window:
            if abs(mid - leg.strike) <= band:
                return GuardResult(outcome=GuardOutcome.REJECT, reason="pin_risk")
        return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)
```

- [ ] **Step 8: Run pin-risk test, watch it pass**

```bash
uv run pytest tests/test_guards_pin_risk.py -v
```

Expected: 4 passed.

- [ ] **Step 9: Commit**

```bash
git add src/trading_assistant/brain/guards/__init__.py \
        src/trading_assistant/brain/guards/spread.py \
        src/trading_assistant/brain/guards/pin_risk.py \
        tests/test_guards_spread.py tests/test_guards_pin_risk.py
git commit -m "feat(brain): add SpreadGuard and PinRiskGuard"
```

---

## Task 14: Guards — event window + caps

**Files:**
- Create: `src/trading_assistant/brain/guards/event_window.py`
- Create: `src/trading_assistant/brain/guards/caps.py`
- Create: `tests/test_guards_event_window.py`
- Create: `tests/test_guards_caps.py`

**Event-window guard**: rejects intents whose expiry straddles a high-impact event (FOMC/CPI/NFP) on the underlying. The rationale: those events cause violent IV moves that wreck spreads.

**Caps**: two guards rolled together.
- `IdeaCapGuard`: counts validated intents created today; rejects further intents once the cap is reached (default 2). Per spec section 5.4: rejected ideas still get written to the audit log; they just don't get surfaced to the user. The guard's job is to fail anything past the cap.
- `DailyLossCapGuard`: reads cumulative paper P&L for today from `app_state`; rejects if the loss cap has already been hit. (Phase 2 doesn't have realized P&L yet — Phase 4 adds it — so this guard reads an `app_state["daily_realized_pnl_usd"]` key that defaults to `0.0`.)

- [ ] **Step 1: Write the failing event-window test**

`tests/test_guards_event_window.py`:

```python
"""EventWindowGuard tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.guards.event_window import EventWindowGuard
from trading_assistant.brain.validator import GuardOutcome
from trading_assistant.calendars.events import EconomicEvent, EventCalendar, EventKind
from trading_assistant.intents.model import Leg, Strategy, TradeIntent


def _intent(expiry: dt.date, symbol: str = "SPY") -> TradeIntent:
    return TradeIntent(
        id="i", created_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
        signal_ids=["s"], symbol=symbol, strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=740.0, expiry=expiry, qty=1)],
        rationale_md="x", max_loss_usd=200.0, max_gain_usd=None, confidence=0.5,
    )


def test_rejects_when_expiry_straddles_fomc():
    cal = EventCalendar(events=[
        EconomicEvent(kind=EventKind.FOMC, date=dt.date(2026, 5, 14),
                      symbols=frozenset({"SPY", "QQQ"})),
    ])
    guard = EventWindowGuard(calendar=cal,
                              now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    res = guard.check(_intent(expiry=dt.date(2026, 5, 16)))
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "event_window"


def test_accepts_when_expiry_before_event():
    cal = EventCalendar(events=[
        EconomicEvent(kind=EventKind.FOMC, date=dt.date(2026, 5, 14),
                      symbols=frozenset({"SPY"})),
    ])
    guard = EventWindowGuard(calendar=cal,
                              now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    assert guard.check(_intent(expiry=dt.date(2026, 5, 13))).outcome == GuardOutcome.ACCEPT


def test_accepts_when_event_affects_different_symbol():
    cal = EventCalendar(events=[
        EconomicEvent(kind=EventKind.EARNINGS, date=dt.date(2026, 5, 14),
                      symbols=frozenset({"NVDA"})),
    ])
    guard = EventWindowGuard(calendar=cal,
                              now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    assert guard.check(_intent(expiry=dt.date(2026, 5, 16))).outcome == GuardOutcome.ACCEPT
```

- [ ] **Step 2: Run event test, watch it fail**

```bash
uv run pytest tests/test_guards_event_window.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `EventWindowGuard`**

Create `src/trading_assistant/brain/guards/event_window.py`:

```python
"""EventWindowGuard: reject if expiry crosses a macro/earnings event for the symbol."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.validator import GuardOutcome, GuardResult
from trading_assistant.calendars.events import EventCalendar
from trading_assistant.intents.model import TradeIntent


class EventWindowGuard:
    name = "event_window"

    def __init__(self, calendar: EventCalendar, now: dt.datetime) -> None:
        self._cal = calendar
        self._now = now

    def check(self, intent: TradeIntent) -> GuardResult:
        today = self._now.date()
        for leg in intent.legs:
            events = self._cal.events_in_window(today, leg.expiry)
            for ev in events:
                if intent.symbol in ev.symbols and today < ev.date <= leg.expiry:
                    return GuardResult(outcome=GuardOutcome.REJECT, reason="event_window")
        return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)
```

- [ ] **Step 4: Run event test, watch it pass**

```bash
uv run pytest tests/test_guards_event_window.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Write the failing caps test**

`tests/test_guards_caps.py`:

```python
"""IdeaCapGuard + DailyLossCapGuard tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.guards.caps import DailyLossCapGuard, IdeaCapGuard
from trading_assistant.brain.validator import GuardOutcome
from trading_assistant.db.repositories import AppStateRepo
from trading_assistant.db.schema import create_schema
from trading_assistant.intents.model import Leg, Strategy, TradeIntent
from trading_assistant.intents.repo import TradeIntentRepo


def _intent(intent_id: str, now: dt.datetime) -> TradeIntent:
    return TradeIntent(
        id=intent_id, created_at=now,
        signal_ids=["s"], symbol="SPY", strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=740.0,
                   expiry=dt.date(2026, 6, 19), qty=1)],
        rationale_md="x", max_loss_usd=200.0, max_gain_usd=None, confidence=0.5,
    )


def test_idea_cap_accepts_when_under_cap(db_conn):
    create_schema(db_conn)
    repo = TradeIntentRepo(db_conn)
    now = dt.datetime(2026, 5, 11, 14, tzinfo=dt.timezone.utc)
    guard = IdeaCapGuard(intent_repo=repo, cap=2, now=now)
    assert guard.check(_intent("i1", now)).outcome == GuardOutcome.ACCEPT


def test_idea_cap_rejects_when_cap_reached(db_conn):
    create_schema(db_conn)
    # Seed two already-validated intents for today.
    from trading_assistant.signals.model import Signal, SignalKind
    from trading_assistant.signals.repo import SignalRepo
    sig_repo = SignalRepo(db_conn)
    sig_repo.write(Signal(id="s", kind=SignalKind.NEWS_CATALYST, symbol="SPY",
                          created_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
                          strength=0.5, evidence={}))
    repo = TradeIntentRepo(db_conn)
    now = dt.datetime(2026, 5, 11, 14, tzinfo=dt.timezone.utc)
    repo.write(_intent("i1", now), status="validated", rejection_reason=None)
    repo.write(_intent("i2", now), status="validated", rejection_reason=None)
    guard = IdeaCapGuard(intent_repo=repo, cap=2, now=now)
    new_intent = _intent("i3", now)
    res = guard.check(new_intent)
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "idea_cap_reached"


def test_idea_cap_ignores_rejected_intents(db_conn):
    create_schema(db_conn)
    from trading_assistant.signals.model import Signal, SignalKind
    from trading_assistant.signals.repo import SignalRepo
    SignalRepo(db_conn).write(Signal(id="s", kind=SignalKind.NEWS_CATALYST, symbol="SPY",
                                      created_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
                                      strength=0.5, evidence={}))
    repo = TradeIntentRepo(db_conn)
    now = dt.datetime(2026, 5, 11, 14, tzinfo=dt.timezone.utc)
    repo.write(_intent("i1", now), status="rejected", rejection_reason="spread_too_wide")
    repo.write(_intent("i2", now), status="rejected", rejection_reason="pin_risk")
    guard = IdeaCapGuard(intent_repo=repo, cap=2, now=now)
    assert guard.check(_intent("i3", now)).outcome == GuardOutcome.ACCEPT


def test_daily_loss_cap_accepts_when_under_threshold(db_conn):
    create_schema(db_conn)
    AppStateRepo(db_conn).set("daily_realized_pnl_usd", "-100.0")
    guard = DailyLossCapGuard(state_repo=AppStateRepo(db_conn), loss_cap_usd=500.0)
    now = dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc)
    assert guard.check(_intent("i", now)).outcome == GuardOutcome.ACCEPT


def test_daily_loss_cap_rejects_when_loss_exceeds_cap(db_conn):
    create_schema(db_conn)
    AppStateRepo(db_conn).set("daily_realized_pnl_usd", "-600.0")
    guard = DailyLossCapGuard(state_repo=AppStateRepo(db_conn), loss_cap_usd=500.0)
    now = dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc)
    res = guard.check(_intent("i", now))
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "daily_loss_cap_hit"


def test_daily_loss_cap_treats_missing_state_as_zero(db_conn):
    create_schema(db_conn)
    guard = DailyLossCapGuard(state_repo=AppStateRepo(db_conn), loss_cap_usd=500.0)
    now = dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc)
    assert guard.check(_intent("i", now)).outcome == GuardOutcome.ACCEPT
```

- [ ] **Step 6: Run caps test, watch it fail**

```bash
uv run pytest tests/test_guards_caps.py -v
```

Expected: ImportError.

- [ ] **Step 7: Implement `IdeaCapGuard` + `DailyLossCapGuard`**

Create `src/trading_assistant/brain/guards/caps.py`:

```python
"""Caps guards: per-day idea count cap and per-day realized-loss cap."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.validator import GuardOutcome, GuardResult
from trading_assistant.db.repositories import AppStateRepo
from trading_assistant.intents.model import TradeIntent
from trading_assistant.intents.repo import TradeIntentRepo


class IdeaCapGuard:
    name = "idea_cap"

    def __init__(self, intent_repo: TradeIntentRepo, cap: int, now: dt.datetime) -> None:
        self._repo = intent_repo
        self._cap = cap
        self._now = now

    def check(self, intent: TradeIntent) -> GuardResult:
        today_start = dt.datetime(self._now.year, self._now.month, self._now.day,
                                   tzinfo=dt.timezone.utc)
        rows = self._repo.list_since(today_start)
        validated_today = sum(1 for r in rows if r.status == "validated")
        if validated_today >= self._cap:
            return GuardResult(outcome=GuardOutcome.REJECT, reason="idea_cap_reached")
        return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)


class DailyLossCapGuard:
    name = "daily_loss_cap"

    def __init__(self, state_repo: AppStateRepo, loss_cap_usd: float) -> None:
        self._state = state_repo
        self._cap = loss_cap_usd

    def check(self, intent: TradeIntent) -> GuardResult:
        raw = self._state.get("daily_realized_pnl_usd")
        pnl = float(raw) if raw is not None else 0.0
        if pnl <= -self._cap:
            return GuardResult(outcome=GuardOutcome.REJECT, reason="daily_loss_cap_hit")
        return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)
```

- [ ] **Step 8: Run caps test, watch it pass**

```bash
uv run pytest tests/test_guards_caps.py -v
```

Expected: 6 passed.

- [ ] **Step 9: Run the full test suite**

```bash
uv run pytest -q
```

Expected: all green (this should bring the total past ~95 tests).

- [ ] **Step 10: Commit**

```bash
git add src/trading_assistant/brain/guards/event_window.py \
        src/trading_assistant/brain/guards/caps.py \
        tests/test_guards_event_window.py tests/test_guards_caps.py
git commit -m "feat(brain): add EventWindowGuard, IdeaCapGuard, DailyLossCapGuard"
```

---

## Task 15: CLI `synthesize` command — end-to-end

**Files:**
- Modify: `src/trading_assistant/cli.py`
- Create: `tests/test_cli_synthesize.py`

Adds a second command to the CLI: `synthesize`. Wires together everything from Phase 1 + Phase 2:
1. Ingest fresh snapshot (reuses Phase 1's pipeline)
2. Run all four signal generators, persist signals
3. Synthesize candidate intents via Claude
4. Validate each candidate, persisting both accepts and rejects with reasons
5. Print accepted intents (the others are in the audit log for inspection)

Since the CLI now has two commands, we need to give each one a name (Typer collapses the root only when there's one).

- [ ] **Step 1: Write the failing CLI test**

`tests/test_cli_synthesize.py`:

```python
"""CLI synthesize command smoke test (with all externals mocked)."""

from __future__ import annotations

from typer.testing import CliRunner

from trading_assistant.cli import app


def test_cli_help_lists_synthesize_command():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "synthesize" in result.stdout
    assert "snapshot" in result.stdout
```

- [ ] **Step 2: Run CLI test, watch it fail**

```bash
uv run pytest tests/test_cli_synthesize.py -v
```

Expected: assertion fails (synthesize not in help) OR succeeds trivially if the test file was already there. If the previous test file already exists with content, replace it.

- [ ] **Step 3: Extend the CLI**

Replace the contents of `src/trading_assistant/cli.py` with:

```python
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
    """Run ingest → signals → LLM synthesize → validate. Print accepted intents."""
    import anthropic

    from trading_assistant.brain.anthropic_client import AnthropicClient
    from trading_assistant.brain.guards.caps import DailyLossCapGuard, IdeaCapGuard
    from trading_assistant.brain.guards.event_window import EventWindowGuard
    from trading_assistant.brain.guards.pin_risk import PinRiskGuard
    from trading_assistant.brain.guards.spread import SpreadGuard
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

    candidates = synth.synthesize(signals=all_signals, quotes=quotes,
                                   recent_news=recent_news, now=now)

    intent_repo = TradeIntentRepo(conn)
    validator = Validator(guards=[
        SpreadGuard(chain_client=oc, max_pct=cfg.max_spread_pct_of_mid),
        PinRiskGuard(quote_client=md, pin_pct=cfg.pin_risk_pct, now=now),
        EventWindowGuard(calendar=event_cal, now=now),
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
```

- [ ] **Step 4: Run CLI test, watch it pass**

```bash
uv run pytest tests/test_cli_synthesize.py -v
uv run pytest tests/test_cli_snapshot.py -v
```

Expected: both pass.

- [ ] **Step 5: Run the full suite**

```bash
uv run pytest -q
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/trading_assistant/cli.py tests/test_cli_synthesize.py
git commit -m "feat(cli): add synthesize command for end-to-end signals → ideas → validation"
```

---

## Task 16: Manual end-to-end smoke test

**Files:** none.

This is a manual checkout, mirroring Task 15 of Phase 1. The user runs `synthesize` against live APIs (Alpaca + Yahoo + FRED + Finnhub + Anthropic) and confirms the pipeline works end-to-end.

**Pre-requisites (user must have):**
- `.env` from Phase 1 already populated with real Alpaca/FRED/Finnhub keys
- A **real** Anthropic API key replacing the Phase 1 placeholder
- `config.yaml` from Phase 1

- [ ] **Step 1: Confirm a real Anthropic key is set**

```bash
grep '^ANTHROPIC_API_KEY=' ~/.config/trading-assistant/.env
```

The value must start with `sk-ant-`. If it's the Phase 1 placeholder, update it from https://console.anthropic.com/.

- [ ] **Step 2: Run the synthesize pipeline**

```bash
uv run trading-assistant synthesize \
  --config ~/.config/trading-assistant/config.yaml \
  --env ~/.config/trading-assistant/.env \
  --db ./data/app.db
```

Expected output: a summary of signal counts per generator, candidate count, and accepted/rejected counts. If any intent is accepted, it prints the strategy, legs, max loss/gain, and rationale.

- [ ] **Step 3: Verify SQLite contents**

```bash
sqlite3 ./data/app.db <<'EOF'
.mode column
.headers on
SELECT kind, COUNT(*) AS n FROM signals
  WHERE created_at >= date('now', '-1 day')
  GROUP BY kind;
SELECT status, rejection_reason, COUNT(*) AS n FROM trade_intents
  WHERE created_at >= date('now', '-1 day')
  GROUP BY status, rejection_reason;
EOF
```

Expected: at least one signal row per generator that found something, and (if Claude produced candidates) one or more `trade_intents` rows.

- [ ] **Step 4: Manual quality check**

Read each accepted rationale aloud. Ask:
- Does the thesis cite a specific signal?
- Is the strike + expiry choice plausible given the underlying mid?
- Would a competent human option trader accept this idea on its face?

If "no" to any of these, capture the issue and we iterate on prompt or guards before moving to Phase 3. **No code change required during the smoke test itself** — observations only.

- [ ] **Step 5: Mark task complete**

There's no commit for this task — it's a verification step. Report results back to the controller.

---

## Self-Review

After writing this plan, I checked against the spec:

1. **Spec coverage** (per design section 5):
   - 5.2 Signal generators (technicals, volatility, news catalysts) → Tasks 4, 6, 7, 8 ✓
   - 5.3 LLM reasoning (Anthropic with prompt caching, hard token cap, citation requirement) → Tasks 10, 11 ✓
   - 5.4 Idea validator (allowlist, spread guard, event-window, pin-risk for ≤7d, daily idea cap, daily loss cap) → Tasks 12, 13, 14 ✓
   - 5.5 Trade executor → Phase 4 (not in this plan) ✓
   - 5.10 Audit log: every rejection is recorded via `TradeIntentRepo.write(status="rejected", rejection_reason=...)` ✓

2. **Placeholder scan**: No "TBD", no "add appropriate error handling," no "similar to Task N." Every code block is complete.

3. **Type consistency**:
   - `Signal.symbol` is uppercased in model.py, and every generator passes through `_upper()` on input — consistent.
   - `TradeIntent.legs` is `list[Leg]` everywhere; `Strategy` enum used uniformly.
   - `GuardResult` and `GuardOutcome` defined in `validator.py` and imported the same way in every guard module.
   - `BarSource` signature `daily_bars(symbol, start: date, end: date) -> list[Bar]` is consistent between the Protocol, the Alpaca adapter, and the test fakes.

4. **One gap noted and resolved**: `EventCalendar` is wired in `cli.py` with an empty `events=[]`. This is deliberate: Phase 2 ships with no live event-data source (the spec listed it as TBD for the foundation). The guards work correctly with an empty calendar (everything passes the event window). Phase 3 adds an event data adapter.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-11-phase-2-brain.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, two-stage review between tasks, fast iteration. This is what we used in Phase 1; pattern is proven.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints for review.

**Which approach?**
