# Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the project skeleton, persistence layer, market/event calendars, and all data ingestion clients, with a CLI that runs a "snapshot" command end-to-end against real free APIs.

**Architecture:** Single Python package, `src/` layout, sync code throughout Phase 1 (async arrives in Phase 3 with FastAPI). Persistence is SQLite in WAL mode via stdlib `sqlite3` (no ORM). External I/O is wrapped in narrow client classes with dependency-injectable HTTP/SDK objects so tests can mock cleanly.

**Tech Stack:**
- Python 3.11+
- `uv` (package + venv manager — single binary, fast)
- `typer` (CLI)
- `pydantic` v2 (data models)
- `structlog` (structured logging)
- `pyyaml` (config)
- `python-dotenv` (secrets loading)
- `pandas-market-calendars` (NYSE calendar)
- `alpaca-py` (Alpaca SDK)
- `yfinance` (Yahoo options chains)
- `fredapi` (FRED economic data)
- `feedparser` (RSS)
- `httpx` (HTTP client for Finnhub)
- `pytest`, `pytest-mock`, `respx` (testing)
- `freezegun` (time mocking)

**Conventions:**
- TDD: failing test → minimal impl → passing test → commit
- Files stay focused; if a file grows past ~250 lines, split it
- All external I/O behind a class with an injectable HTTP client / SDK
- Logging via `structlog`; never `print` in library code

---

## File Structure (created in this plan)

```
trading_assistant/
├── pyproject.toml                              # Task 1
├── README.md                                   # Task 1
├── .gitignore                                  # Task 1
├── .env.example                                # Task 4
├── config.yaml.example                         # Task 3
├── src/trading_assistant/
│   ├── __init__.py                             # Task 1
│   ├── __main__.py                             # Task 14
│   ├── cli.py                                  # Task 14
│   ├── logging_setup.py                        # Task 2
│   ├── config.py                               # Task 3
│   ├── secrets.py                              # Task 4
│   ├── db/
│   │   ├── __init__.py                         # Task 5
│   │   ├── connection.py                       # Task 5
│   │   ├── schema.py                           # Task 6
│   │   └── repositories.py                     # Task 7
│   ├── calendars/
│   │   ├── __init__.py                         # Task 8
│   │   ├── market.py                           # Task 8
│   │   └── events.py                           # Task 9
│   └── ingest/
│       ├── __init__.py                         # Task 10
│       ├── market_data.py                      # Task 10
│       ├── options_chain.py                    # Task 11
│       ├── economic.py                         # Task 12
│       └── news.py                             # Task 13
└── tests/
    ├── conftest.py                             # Task 5
    ├── test_logging_setup.py                   # Task 2
    ├── test_config.py                          # Task 3
    ├── test_secrets.py                         # Task 4
    ├── test_db_connection.py                   # Task 5
    ├── test_db_schema.py                       # Task 6
    ├── test_db_repositories.py                 # Task 7
    ├── test_calendars_market.py                # Task 8
    ├── test_calendars_events.py                # Task 9
    ├── test_ingest_market_data.py              # Task 10
    ├── test_ingest_options_chain.py            # Task 11
    ├── test_ingest_economic.py                 # Task 12
    ├── test_ingest_news.py                     # Task 13
    └── test_cli_snapshot.py                    # Task 14
```

---

## Task 1: Project skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `.gitignore`
- Create: `src/trading_assistant/__init__.py`

- [ ] **Step 1.1: Initialize uv project structure**

Run:
```bash
mkdir -p src/trading_assistant tests docs/superpowers/{specs,plans}
touch src/trading_assistant/__init__.py tests/__init__.py
```

- [ ] **Step 1.2: Write `pyproject.toml`**

```toml
[project]
name = "trading-assistant"
version = "0.1.0"
description = "Local options trading assistant for SPY/QQQ/IWM/DIA"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12",
    "pydantic>=2.6",
    "structlog>=24.1",
    "pyyaml>=6.0",
    "python-dotenv>=1.0",
    "pandas-market-calendars>=4.4",
    "alpaca-py>=0.30",
    "yfinance>=0.2.40",
    "fredapi>=0.5",
    "feedparser>=6.0",
    "httpx>=0.27",
]

[project.scripts]
trading-assistant = "trading_assistant.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/trading_assistant"]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
    "respx>=0.21",
    "freezegun>=1.5",
    "ruff>=0.4",
    "mypy>=1.10",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N"]

[tool.mypy]
python_version = "3.11"
strict = true
files = ["src"]
```

- [ ] **Step 1.3: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/
dist/
build/
.env
*.db
*.db-journal
*.db-wal
*.db-shm
.coverage
htmlcov/
```

- [ ] **Step 1.4: Write minimal `README.md`**

```markdown
# Trading Assistant

Local options trading assistant for SPY/QQQ/IWM/DIA.

## Install

```
brew install uv
uv sync
```

## Usage

```
uv run trading-assistant --help
```

See `docs/superpowers/specs/` for the full design.
```

- [ ] **Step 1.5: Write `src/trading_assistant/__init__.py`**

```python
"""Local options trading assistant."""

__version__ = "0.1.0"
```

- [ ] **Step 1.6: Verify uv can sync**

Run: `uv sync`
Expected: A `.venv/` directory is created and dependencies install. If `uv` is not installed, run `brew install uv` first.

- [ ] **Step 1.7: Commit**

```bash
git add pyproject.toml README.md .gitignore src tests
git commit -m "chore: initialize trading-assistant project skeleton"
```

---

## Task 2: Logging setup

**Files:**
- Create: `src/trading_assistant/logging_setup.py`
- Test: `tests/test_logging_setup.py`

- [ ] **Step 2.1: Write the failing test**

Create `tests/test_logging_setup.py`:
```python
import json
import logging

import structlog

from trading_assistant.logging_setup import configure_logging


def test_configure_logging_emits_json_with_required_fields(capsys):
    configure_logging(level="INFO", json_output=True)
    log = structlog.get_logger("test")
    log.info("hello", count=3)
    captured = capsys.readouterr()
    record = json.loads(captured.out.strip().splitlines()[-1])
    assert record["event"] == "hello"
    assert record["count"] == 3
    assert record["level"] == "info"
    assert "timestamp" in record


def test_configure_logging_respects_level(capsys):
    configure_logging(level="WARNING", json_output=True)
    log = structlog.get_logger("test")
    log.info("debug-level should be hidden")
    log.warning("warn-level should appear")
    captured = capsys.readouterr()
    assert "debug-level" not in captured.out
    assert "warn-level" in captured.out
```

- [ ] **Step 2.2: Run test to verify it fails**

Run: `uv run pytest tests/test_logging_setup.py -v`
Expected: FAIL with `ImportError: cannot import name 'configure_logging' from 'trading_assistant.logging_setup'`

- [ ] **Step 2.3: Implement `logging_setup.py`**

Create `src/trading_assistant/logging_setup.py`:
```python
"""Structured logging configuration for the trading assistant."""

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    """Configure structlog + stdlib logging once at process start."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

- [ ] **Step 2.4: Run tests to verify pass**

Run: `uv run pytest tests/test_logging_setup.py -v`
Expected: 2 passed.

- [ ] **Step 2.5: Commit**

```bash
git add src/trading_assistant/logging_setup.py tests/test_logging_setup.py
git commit -m "feat(logging): add structured JSON logging setup"
```

---

## Task 3: Config loading

**Files:**
- Create: `src/trading_assistant/config.py`
- Create: `config.yaml.example`
- Test: `tests/test_config.py`

- [ ] **Step 3.1: Write the failing test**

Create `tests/test_config.py`:
```python
from pathlib import Path

import pytest

from trading_assistant.config import AppConfig, ConfigError, load_config


def write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return p


def test_load_config_returns_defaults_when_file_minimal(tmp_path: Path):
    cfg_path = write_yaml(tmp_path, "mode: paper\n")
    cfg = load_config(cfg_path)
    assert isinstance(cfg, AppConfig)
    assert cfg.mode == "paper"
    assert cfg.daily_idea_cap == 2
    assert cfg.daily_loss_cap_usd == 500.0
    assert cfg.universe == ["SPY", "QQQ", "IWM", "DIA"]
    assert cfg.max_spread_pct_of_mid == 0.05


def test_load_config_overrides_defaults(tmp_path: Path):
    cfg_path = write_yaml(
        tmp_path,
        "mode: paper\ndaily_idea_cap: 5\ndaily_loss_cap_usd: 1000\nmax_spread_pct_of_mid: 0.1\n",
    )
    cfg = load_config(cfg_path)
    assert cfg.daily_idea_cap == 5
    assert cfg.daily_loss_cap_usd == 1000.0
    assert cfg.max_spread_pct_of_mid == 0.1


def test_load_config_rejects_live_mode_in_phase_1(tmp_path: Path):
    cfg_path = write_yaml(tmp_path, "mode: live\n")
    with pytest.raises(ConfigError, match="live mode is not yet supported"):
        load_config(cfg_path)


def test_load_config_missing_file_raises(tmp_path: Path):
    with pytest.raises(ConfigError, match="config file not found"):
        load_config(tmp_path / "missing.yaml")
```

- [ ] **Step 3.2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with import error.

- [ ] **Step 3.3: Implement `config.py`**

Create `src/trading_assistant/config.py`:
```python
"""Application configuration loading."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError


class ConfigError(Exception):
    """Raised when configuration cannot be loaded or is invalid."""


class AppConfig(BaseModel):
    mode: Literal["paper"] = "paper"
    universe: list[str] = Field(default_factory=lambda: ["SPY", "QQQ", "IWM", "DIA"])
    daily_idea_cap: int = 2
    daily_loss_cap_usd: float = 500.0
    max_spread_pct_of_mid: float = 0.05
    pin_risk_pct: float = 0.015
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "07:00"
    timezone: str = "America/New_York"
    log_level: str = "INFO"
    log_json: bool = True


def load_config(path: Path) -> AppConfig:
    """Load and validate the YAML config at ``path``."""
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    raw = yaml.safe_load(path.read_text()) or {}
    if raw.get("mode") == "live":
        raise ConfigError("live mode is not yet supported in this phase")
    try:
        return AppConfig(**raw)
    except ValidationError as exc:
        raise ConfigError(f"invalid config: {exc}") from exc
```

- [ ] **Step 3.4: Write `config.yaml.example`**

```yaml
# trading-assistant configuration. Copy to ~/.config/trading-assistant/config.yaml.

mode: paper                       # Phase 1 supports paper only.
universe: [SPY, QQQ, IWM, DIA]
daily_idea_cap: 2
daily_loss_cap_usd: 500.0
max_spread_pct_of_mid: 0.05
pin_risk_pct: 0.015
quiet_hours_start: "22:00"
quiet_hours_end: "07:00"
timezone: "America/New_York"
log_level: INFO
log_json: true
```

- [ ] **Step 3.5: Run tests to verify pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: 4 passed.

- [ ] **Step 3.6: Commit**

```bash
git add src/trading_assistant/config.py config.yaml.example tests/test_config.py
git commit -m "feat(config): add YAML config loading with paper-only enforcement"
```

---

## Task 4: Secrets loading

**Files:**
- Create: `src/trading_assistant/secrets.py`
- Create: `.env.example`
- Test: `tests/test_secrets.py`

- [ ] **Step 4.1: Write the failing test**

Create `tests/test_secrets.py`:
```python
from pathlib import Path

import pytest

from trading_assistant.secrets import Secrets, SecretsError, load_secrets


def write_env(tmp_path: Path, body: str) -> Path:
    p = tmp_path / ".env"
    p.write_text(body)
    return p


def test_load_secrets_returns_all_required_keys(tmp_path: Path):
    env = write_env(
        tmp_path,
        "ALPACA_API_KEY=ak\nALPACA_SECRET_KEY=sk\nFRED_API_KEY=fk\n"
        "FINNHUB_API_KEY=fnk\nANTHROPIC_API_KEY=anth\nPUSHOVER_USER_KEY=puk\n"
        "PUSHOVER_APP_TOKEN=pat\n",
    )
    s = load_secrets(env)
    assert isinstance(s, Secrets)
    assert s.alpaca_api_key == "ak"
    assert s.alpaca_secret_key == "sk"
    assert s.fred_api_key == "fk"
    assert s.finnhub_api_key == "fnk"
    assert s.anthropic_api_key == "anth"
    assert s.pushover_user_key == "puk"
    assert s.pushover_app_token == "pat"


def test_load_secrets_rejects_missing_file(tmp_path: Path):
    with pytest.raises(SecretsError, match="secrets file not found"):
        load_secrets(tmp_path / "missing.env")


def test_load_secrets_rejects_missing_keys(tmp_path: Path):
    env = write_env(tmp_path, "ALPACA_API_KEY=ak\n")
    with pytest.raises(SecretsError, match="missing required keys"):
        load_secrets(env)


def test_load_secrets_repr_redacts_values(tmp_path: Path):
    env = write_env(
        tmp_path,
        "ALPACA_API_KEY=ak\nALPACA_SECRET_KEY=sk\nFRED_API_KEY=fk\n"
        "FINNHUB_API_KEY=fnk\nANTHROPIC_API_KEY=anth\nPUSHOVER_USER_KEY=puk\n"
        "PUSHOVER_APP_TOKEN=pat\n",
    )
    s = load_secrets(env)
    text = repr(s)
    for value in ("ak", "sk", "fk", "fnk", "anth", "puk", "pat"):
        assert value not in text
    assert "REDACTED" in text
```

- [ ] **Step 4.2: Run test to verify it fails**

Run: `uv run pytest tests/test_secrets.py -v`
Expected: FAIL with import error.

- [ ] **Step 4.3: Implement `secrets.py`**

Create `src/trading_assistant/secrets.py`:
```python
"""Secrets loading from a .env file. Never log or pickle these values."""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

from dotenv import dotenv_values


class SecretsError(Exception):
    """Raised when secrets cannot be loaded."""


REQUIRED_KEYS = (
    "ALPACA_API_KEY",
    "ALPACA_SECRET_KEY",
    "FRED_API_KEY",
    "FINNHUB_API_KEY",
    "ANTHROPIC_API_KEY",
    "PUSHOVER_USER_KEY",
    "PUSHOVER_APP_TOKEN",
)


@dataclass(frozen=True)
class Secrets:
    alpaca_api_key: str
    alpaca_secret_key: str
    fred_api_key: str
    finnhub_api_key: str
    anthropic_api_key: str
    pushover_user_key: str
    pushover_app_token: str

    def __repr__(self) -> str:
        names = [f.name for f in fields(self)]
        return "Secrets(" + ", ".join(f"{n}=REDACTED" for n in names) + ")"


def load_secrets(path: Path) -> Secrets:
    if not path.exists():
        raise SecretsError(f"secrets file not found: {path}")
    raw = {k: v for k, v in dotenv_values(path).items() if v is not None}
    missing = [k for k in REQUIRED_KEYS if k not in raw]
    if missing:
        raise SecretsError(f"missing required keys: {missing}")
    return Secrets(
        alpaca_api_key=raw["ALPACA_API_KEY"],
        alpaca_secret_key=raw["ALPACA_SECRET_KEY"],
        fred_api_key=raw["FRED_API_KEY"],
        finnhub_api_key=raw["FINNHUB_API_KEY"],
        anthropic_api_key=raw["ANTHROPIC_API_KEY"],
        pushover_user_key=raw["PUSHOVER_USER_KEY"],
        pushover_app_token=raw["PUSHOVER_APP_TOKEN"],
    )
```

- [ ] **Step 4.4: Write `.env.example`**

```
# Copy to ~/.config/trading-assistant/.env and chmod 600.
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
FRED_API_KEY=
FINNHUB_API_KEY=
ANTHROPIC_API_KEY=
PUSHOVER_USER_KEY=
PUSHOVER_APP_TOKEN=
```

- [ ] **Step 4.5: Run tests to verify pass**

Run: `uv run pytest tests/test_secrets.py -v`
Expected: 4 passed.

- [ ] **Step 4.6: Commit**

```bash
git add src/trading_assistant/secrets.py .env.example tests/test_secrets.py
git commit -m "feat(secrets): add .env loader with required-key validation and repr redaction"
```

---

## Task 5: SQLite connection (WAL mode)

**Files:**
- Create: `src/trading_assistant/db/__init__.py`
- Create: `src/trading_assistant/db/connection.py`
- Create: `tests/conftest.py`
- Test: `tests/test_db_connection.py`

- [ ] **Step 5.1: Write the failing test**

Create `tests/test_db_connection.py`:
```python
import sqlite3
from pathlib import Path

from trading_assistant.db.connection import open_connection


def test_open_connection_enables_wal_mode(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = open_connection(db_path)
    cur = conn.execute("PRAGMA journal_mode;")
    mode = cur.fetchone()[0]
    assert mode.lower() == "wal"
    conn.close()


def test_open_connection_enables_foreign_keys(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = open_connection(db_path)
    cur = conn.execute("PRAGMA foreign_keys;")
    assert cur.fetchone()[0] == 1
    conn.close()


def test_open_connection_returns_row_factory_dict(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = open_connection(db_path)
    conn.execute("CREATE TABLE t (a INTEGER, b TEXT)")
    conn.execute("INSERT INTO t VALUES (1, 'x')")
    row = conn.execute("SELECT * FROM t").fetchone()
    assert row["a"] == 1
    assert row["b"] == "x"
    conn.close()


def test_open_connection_creates_parent_dir(tmp_path: Path):
    db_path = tmp_path / "nested" / "dir" / "test.db"
    conn = open_connection(db_path)
    assert db_path.parent.is_dir()
    assert isinstance(conn, sqlite3.Connection)
    conn.close()
```

- [ ] **Step 5.2: Run test to verify it fails**

Run: `uv run pytest tests/test_db_connection.py -v`
Expected: FAIL with import error.

- [ ] **Step 5.3: Implement `db/connection.py`**

Create `src/trading_assistant/db/__init__.py`:
```python
"""Persistence layer."""
```

Create `src/trading_assistant/db/connection.py`:
```python
"""SQLite connection helpers. WAL mode is mandatory."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def open_connection(path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode and foreign keys enabled.

    Why WAL: the spec requires it because multiple cycle jobs and HTTP
    handlers will write concurrently in later phases. WAL avoids
    'database is locked' errors under modest contention.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None)  # autocommit
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn
```

- [ ] **Step 5.4: Write shared `conftest.py`**

Create `tests/conftest.py`:
```python
"""Shared pytest fixtures."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from trading_assistant.db.connection import open_connection


@pytest.fixture
def db_conn(tmp_path: Path) -> sqlite3.Connection:
    """A WAL-mode SQLite connection in a per-test tmp dir."""
    conn = open_connection(tmp_path / "test.db")
    yield conn
    conn.close()
```

- [ ] **Step 5.5: Run tests to verify pass**

Run: `uv run pytest tests/test_db_connection.py -v`
Expected: 4 passed.

- [ ] **Step 5.6: Commit**

```bash
git add src/trading_assistant/db tests/conftest.py tests/test_db_connection.py
git commit -m "feat(db): add WAL-mode SQLite connection helper"
```

---

## Task 6: Database schema

**Files:**
- Create: `src/trading_assistant/db/schema.py`
- Test: `tests/test_db_schema.py`

- [ ] **Step 6.1: Write the failing test**

Create `tests/test_db_schema.py`:
```python
import pytest

from trading_assistant.db.schema import SCHEMA_VERSION, create_schema, current_version


EXPECTED_TABLES = {
    "schema_version",
    "app_state",
    "job_locks",
    "audit_log",
    "signals",
    "trade_intents",
    "paper_orders",
    "fills",
    "news_items",
    "econ_observations",
}


def test_create_schema_is_idempotent(db_conn):
    create_schema(db_conn)
    create_schema(db_conn)  # second call must not raise
    rows = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {r["name"] for r in rows}
    assert EXPECTED_TABLES.issubset(names)


def test_create_schema_records_version(db_conn):
    create_schema(db_conn)
    assert current_version(db_conn) == SCHEMA_VERSION


def test_audit_log_is_append_only_in_practice(db_conn):
    create_schema(db_conn)
    db_conn.execute(
        "INSERT INTO audit_log(kind, payload_json) VALUES (?, ?)",
        ("test", '{"foo": 1}'),
    )
    row = db_conn.execute("SELECT id, kind FROM audit_log").fetchone()
    assert row["kind"] == "test"
    # Schema-level: we don't grant DELETE in any code path; nothing here enforces
    # it via SQL, but assert columns are as expected so a future change requires
    # touching this test.
    cols = {c["name"] for c in db_conn.execute("PRAGMA table_info(audit_log)").fetchall()}
    assert cols == {"id", "kind", "payload_json", "created_at"}


def test_app_state_seeded_with_defaults(db_conn):
    create_schema(db_conn)
    rows = {r["key"]: r["value"] for r in db_conn.execute("SELECT key, value FROM app_state")}
    assert rows["kill_switch"] == "off"
    assert rows["mode"] == "paper"


def test_job_locks_unique_on_name(db_conn):
    create_schema(db_conn)
    db_conn.execute("INSERT INTO job_locks(name, acquired_at) VALUES (?, ?)", ("scan", "t1"))
    with pytest.raises(Exception):
        db_conn.execute("INSERT INTO job_locks(name, acquired_at) VALUES (?, ?)", ("scan", "t2"))
```

- [ ] **Step 6.2: Run test to verify it fails**

Run: `uv run pytest tests/test_db_schema.py -v`
Expected: FAIL with import error.

- [ ] **Step 6.3: Implement `db/schema.py`**

Create `src/trading_assistant/db/schema.py`:
```python
"""Database schema and migration. Single-file DDL for simplicity in Phase 1."""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1

_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS app_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_locks (
    name        TEXT PRIMARY KEY,
    acquired_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    kind         TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_audit_log_kind_created
    ON audit_log(kind, created_at DESC);

CREATE TABLE IF NOT EXISTS signals (
    id              TEXT PRIMARY KEY,           -- uuid4 hex
    created_at      TEXT NOT NULL,
    kind            TEXT NOT NULL,              -- 'trend', 'vol', 'news', etc.
    symbol          TEXT NOT NULL,
    payload_json    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at DESC);

CREATE TABLE IF NOT EXISTS trade_intents (
    id                TEXT PRIMARY KEY,         -- uuid4 hex
    created_at        TEXT NOT NULL,
    signal_id         TEXT NOT NULL REFERENCES signals(id),
    symbol            TEXT NOT NULL,
    structure_json    TEXT NOT NULL,
    rationale_md      TEXT NOT NULL,
    user_thesis       TEXT,
    status            TEXT NOT NULL,            -- 'pending', 'approved', 'rejected', 'submitted'
    rejection_reason  TEXT
);
CREATE INDEX IF NOT EXISTS idx_intents_created ON trade_intents(created_at DESC);

CREATE TABLE IF NOT EXISTS paper_orders (
    client_order_id   TEXT PRIMARY KEY,         -- deterministic from (date, symbol, signal_id)
    intent_id         TEXT NOT NULL REFERENCES trade_intents(id),
    submitted_at      TEXT NOT NULL,
    alpaca_order_id   TEXT,
    status            TEXT NOT NULL,
    raw_response_json TEXT
);

CREATE TABLE IF NOT EXISTS fills (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    client_order_id          TEXT NOT NULL REFERENCES paper_orders(client_order_id),
    filled_at                TEXT NOT NULL,
    qty                      REAL NOT NULL,
    alpaca_fill_price        REAL NOT NULL,
    realistic_fill_price     REAL NOT NULL,    -- worst NBBO + 1 tick
    nbbo_bid                 REAL NOT NULL,
    nbbo_ask                 REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS news_items (
    url_hash       TEXT PRIMARY KEY,
    source         TEXT NOT NULL,
    title          TEXT NOT NULL,
    snippet        TEXT,
    published_at   TEXT,
    arrived_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_news_arrived ON news_items(arrived_at DESC);

CREATE TABLE IF NOT EXISTS econ_observations (
    series_id    TEXT NOT NULL,
    observation_date TEXT NOT NULL,
    value        REAL,
    fetched_at   TEXT NOT NULL,
    PRIMARY KEY (series_id, observation_date)
);
"""

_SEED_APP_STATE = [
    ("kill_switch", "off"),
    ("mode", "paper"),
]


def create_schema(conn: sqlite3.Connection) -> None:
    """Create all tables (idempotent) and record schema version."""
    conn.executescript(_DDL)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version(version) VALUES (?)",
        (SCHEMA_VERSION,),
    )
    for key, value in _SEED_APP_STATE:
        conn.execute(
            "INSERT OR IGNORE INTO app_state(key, value) VALUES (?, ?)",
            (key, value),
        )


def current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    return int(row["v"]) if row and row["v"] is not None else 0
```

- [ ] **Step 6.4: Run tests to verify pass**

Run: `uv run pytest tests/test_db_schema.py -v`
Expected: 5 passed.

- [ ] **Step 6.5: Commit**

```bash
git add src/trading_assistant/db/schema.py tests/test_db_schema.py
git commit -m "feat(db): add schema with signals/intents/orders/fills/news/econ + audit log"
```

---

## Task 7: Repository helpers

**Files:**
- Create: `src/trading_assistant/db/repositories.py`
- Test: `tests/test_db_repositories.py`

- [ ] **Step 7.1: Write the failing test**

Create `tests/test_db_repositories.py`:
```python
import json

import pytest

from trading_assistant.db.repositories import (
    AppStateRepo,
    AuditLogRepo,
    JobLockHeld,
    JobLockRepo,
    NewsRepo,
)
from trading_assistant.db.schema import create_schema


@pytest.fixture
def conn(db_conn):
    create_schema(db_conn)
    return db_conn


def test_app_state_get_and_set(conn):
    repo = AppStateRepo(conn)
    assert repo.get("kill_switch") == "off"
    repo.set("kill_switch", "on")
    assert repo.get("kill_switch") == "on"
    assert repo.get("missing") is None


def test_audit_log_writes_payload(conn):
    repo = AuditLogRepo(conn)
    repo.write("llm_call", {"prompt_tokens": 1234, "model": "claude"})
    rows = list(conn.execute("SELECT kind, payload_json FROM audit_log"))
    assert len(rows) == 1
    assert rows[0]["kind"] == "llm_call"
    assert json.loads(rows[0]["payload_json"]) == {"prompt_tokens": 1234, "model": "claude"}


def test_job_lock_acquire_and_release(conn):
    repo = JobLockRepo(conn)
    with repo.acquire("scan", now="t1"):
        rows = list(conn.execute("SELECT name FROM job_locks"))
        assert {r["name"] for r in rows} == {"scan"}
    rows = list(conn.execute("SELECT name FROM job_locks"))
    assert rows == []


def test_job_lock_double_acquire_raises(conn):
    repo = JobLockRepo(conn)
    with repo.acquire("scan", now="t1"):
        with pytest.raises(JobLockHeld):
            with repo.acquire("scan", now="t2"):
                pass


def test_news_upsert_dedupes(conn):
    repo = NewsRepo(conn)
    repo.upsert(
        url_hash="h1", source="rss", title="t", snippet="s",
        published_at="2026-04-26T13:00:00Z", arrived_at="2026-04-26T13:01:00Z",
    )
    repo.upsert(
        url_hash="h1", source="rss", title="t-different", snippet="s",
        published_at="2026-04-26T13:00:00Z", arrived_at="2026-04-26T14:00:00Z",
    )
    rows = list(conn.execute("SELECT title FROM news_items"))
    assert len(rows) == 1
    assert rows[0]["title"] == "t"  # first write wins on conflict


def test_news_fresh_since_filters(conn):
    repo = NewsRepo(conn)
    repo.upsert(url_hash="a", source="rss", title="old", snippet=None,
                published_at=None, arrived_at="2026-04-26T10:00:00Z")
    repo.upsert(url_hash="b", source="rss", title="new", snippet=None,
                published_at=None, arrived_at="2026-04-26T15:00:00Z")
    fresh = list(repo.fresh_since("2026-04-26T12:00:00Z"))
    titles = {n["title"] for n in fresh}
    assert titles == {"new"}
```

- [ ] **Step 7.2: Run test to verify it fails**

Run: `uv run pytest tests/test_db_repositories.py -v`
Expected: FAIL with import error.

- [ ] **Step 7.3: Implement `db/repositories.py`**

Create `src/trading_assistant/db/repositories.py`:
```python
"""Typed read/write helpers per table. Hand-rolled, no ORM."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Iterator


class JobLockHeld(Exception):
    """Raised when a job lock is already held by someone else."""


class AppStateRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM app_state WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def set(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO app_state(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


class AuditLogRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def write(self, kind: str, payload: dict) -> None:
        self._conn.execute(
            "INSERT INTO audit_log(kind, payload_json) VALUES (?, ?)",
            (kind, json.dumps(payload, separators=(",", ":"), sort_keys=True)),
        )


class JobLockRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @contextmanager
    def acquire(self, name: str, now: str) -> Iterator[None]:
        try:
            self._conn.execute(
                "INSERT INTO job_locks(name, acquired_at) VALUES (?, ?)",
                (name, now),
            )
        except sqlite3.IntegrityError as exc:
            raise JobLockHeld(name) from exc
        try:
            yield
        finally:
            self._conn.execute("DELETE FROM job_locks WHERE name = ?", (name,))


class NewsRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(
        self,
        *,
        url_hash: str,
        source: str,
        title: str,
        snippet: str | None,
        published_at: str | None,
        arrived_at: str,
    ) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO news_items"
            "(url_hash, source, title, snippet, published_at, arrived_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (url_hash, source, title, snippet, published_at, arrived_at),
        )

    def fresh_since(self, iso_timestamp: str) -> Iterator[sqlite3.Row]:
        cur = self._conn.execute(
            "SELECT * FROM news_items WHERE arrived_at > ? ORDER BY arrived_at DESC",
            (iso_timestamp,),
        )
        return iter(cur.fetchall())
```

- [ ] **Step 7.4: Run tests to verify pass**

Run: `uv run pytest tests/test_db_repositories.py -v`
Expected: 6 passed.

- [ ] **Step 7.5: Commit**

```bash
git add src/trading_assistant/db/repositories.py tests/test_db_repositories.py
git commit -m "feat(db): add AppState/AuditLog/JobLock/News repositories"
```

---

## Task 8: Market calendar

**Files:**
- Create: `src/trading_assistant/calendars/__init__.py`
- Create: `src/trading_assistant/calendars/market.py`
- Test: `tests/test_calendars_market.py`

- [ ] **Step 8.1: Write the failing test**

Create `tests/test_calendars_market.py`:
```python
import datetime as dt

from freezegun import freeze_time

from trading_assistant.calendars.market import MarketCalendar


def test_is_open_during_regular_hours():
    cal = MarketCalendar()
    with freeze_time("2026-04-27 14:30:00", tz_offset=0):  # Mon 10:30 ET
        assert cal.is_open_now() is True


def test_is_closed_outside_hours():
    cal = MarketCalendar()
    with freeze_time("2026-04-27 22:00:00", tz_offset=0):  # Mon 18:00 ET
        assert cal.is_open_now() is False


def test_is_closed_on_weekends():
    cal = MarketCalendar()
    with freeze_time("2026-04-25 14:30:00", tz_offset=0):  # Saturday
        assert cal.is_open_now() is False


def test_next_open_returns_future_datetime():
    cal = MarketCalendar()
    with freeze_time("2026-04-25 14:30:00", tz_offset=0):  # Saturday
        nxt = cal.next_open()
        assert nxt > dt.datetime(2026, 4, 25, tzinfo=dt.timezone.utc)
        # Should land on Monday in ET
        assert nxt.astimezone(cal.tz).weekday() == 0


def test_session_bounds_returns_open_close_in_et():
    cal = MarketCalendar()
    open_dt, close_dt = cal.session_bounds(dt.date(2026, 4, 27))
    assert open_dt.astimezone(cal.tz).hour == 9
    assert open_dt.astimezone(cal.tz).minute == 30
    assert close_dt.astimezone(cal.tz).hour == 16
    assert close_dt.astimezone(cal.tz).minute == 0


def test_is_half_day_for_known_holiday():
    cal = MarketCalendar()
    # Day after Thanksgiving 2026 is a half day
    assert cal.is_half_day(dt.date(2026, 11, 27)) is True
    # Random Tuesday is not
    assert cal.is_half_day(dt.date(2026, 4, 28)) is False
```

- [ ] **Step 8.2: Run test to verify it fails**

Run: `uv run pytest tests/test_calendars_market.py -v`
Expected: FAIL with import error.

- [ ] **Step 8.3: Implement `calendars/market.py`**

Create `src/trading_assistant/calendars/__init__.py`:
```python
"""Market and event calendars."""
```

Create `src/trading_assistant/calendars/market.py`:
```python
"""NYSE market calendar wrapper. Always reason in America/New_York, never naive UTC."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pandas as pd
import pandas_market_calendars as mcal


class MarketCalendar:
    def __init__(self) -> None:
        self._cal = mcal.get_calendar("XNYS")
        self.tz = ZoneInfo("America/New_York")

    def _now_utc(self) -> dt.datetime:
        return dt.datetime.now(dt.timezone.utc)

    def is_open_now(self, now: dt.datetime | None = None) -> bool:
        when = now or self._now_utc()
        sched = self._cal.schedule(
            start_date=(when - dt.timedelta(days=1)).date(),
            end_date=(when + dt.timedelta(days=1)).date(),
        )
        if sched.empty:
            return False
        ts = pd.Timestamp(when).tz_convert("UTC") if when.tzinfo else pd.Timestamp(when, tz="UTC")
        return any((row.market_open <= ts <= row.market_close) for row in sched.itertuples())

    def next_open(self, after: dt.datetime | None = None) -> dt.datetime:
        when = after or self._now_utc()
        sched = self._cal.schedule(
            start_date=when.date(),
            end_date=(when + dt.timedelta(days=14)).date(),
        )
        for row in sched.itertuples():
            if row.market_open.to_pydatetime() > when:
                return row.market_open.to_pydatetime()
        raise RuntimeError("no upcoming session within 14 days")

    def session_bounds(self, day: dt.date) -> tuple[dt.datetime, dt.datetime]:
        sched = self._cal.schedule(start_date=day, end_date=day)
        if sched.empty:
            raise ValueError(f"no session on {day}")
        row = next(sched.itertuples())
        return row.market_open.to_pydatetime(), row.market_close.to_pydatetime()

    def is_half_day(self, day: dt.date) -> bool:
        sched = self._cal.schedule(start_date=day, end_date=day)
        if sched.empty:
            return False
        row = next(sched.itertuples())
        # Regular close in ET is 16:00. Half days close earlier (typically 13:00 ET).
        close_et = row.market_close.tz_convert(self.tz)
        return close_et.hour < 16
```

- [ ] **Step 8.4: Run tests to verify pass**

Run: `uv run pytest tests/test_calendars_market.py -v`
Expected: 6 passed. (If `is_half_day_for_known_holiday` fails because the 2026 schedule is not yet finalized in the library version, adjust the date in the test to a confirmed half-day.)

- [ ] **Step 8.5: Commit**

```bash
git add src/trading_assistant/calendars/__init__.py src/trading_assistant/calendars/market.py tests/test_calendars_market.py
git commit -m "feat(calendars): add NYSE market calendar wrapper with half-day detection"
```

---

## Task 9: Event calendar (FOMC/CPI/NFP/earnings)

**Files:**
- Create: `src/trading_assistant/calendars/events.py`
- Test: `tests/test_calendars_events.py`

Phase 1 scope: maintain a static list of upcoming events with the ability to query "is symbol X in an event window over the next N days." Population from external sources is deferred to Phase 2 — for now we expose the data structure and the query.

- [ ] **Step 9.1: Write the failing test**

Create `tests/test_calendars_events.py`:
```python
import datetime as dt

from trading_assistant.calendars.events import (
    EconomicEvent,
    EventCalendar,
    EventKind,
)


def test_event_calendar_returns_empty_when_no_events():
    cal = EventCalendar(events=[])
    assert cal.events_in_window(dt.date(2026, 5, 1), days=5) == []


def test_event_calendar_filters_by_window():
    e1 = EconomicEvent(kind=EventKind.CPI, date=dt.date(2026, 5, 13), symbols={"SPY", "QQQ"})
    e2 = EconomicEvent(kind=EventKind.NFP, date=dt.date(2026, 6, 5), symbols={"IWM"})
    cal = EventCalendar(events=[e1, e2])
    in_window = cal.events_in_window(dt.date(2026, 5, 1), days=14)
    assert in_window == [e1]


def test_symbol_in_event_window_true_for_cpi_on_spy():
    e = EconomicEvent(kind=EventKind.CPI, date=dt.date(2026, 5, 13), symbols={"SPY", "QQQ"})
    cal = EventCalendar(events=[e])
    assert cal.symbol_in_event_window("SPY", dt.date(2026, 5, 12), days=2) is True


def test_symbol_in_event_window_false_for_unrelated_symbol():
    e = EconomicEvent(kind=EventKind.CPI, date=dt.date(2026, 5, 13), symbols={"SPY", "QQQ"})
    cal = EventCalendar(events=[e])
    assert cal.symbol_in_event_window("IWM", dt.date(2026, 5, 12), days=2) is False


def test_symbol_in_event_window_false_outside_window():
    e = EconomicEvent(kind=EventKind.FOMC, date=dt.date(2026, 6, 17), symbols={"SPY"})
    cal = EventCalendar(events=[e])
    assert cal.symbol_in_event_window("SPY", dt.date(2026, 5, 1), days=7) is False
```

- [ ] **Step 9.2: Run test to verify it fails**

Run: `uv run pytest tests/test_calendars_events.py -v`
Expected: FAIL with import error.

- [ ] **Step 9.3: Implement `calendars/events.py`**

Create `src/trading_assistant/calendars/events.py`:
```python
"""Event calendar for FOMC/CPI/NFP/earnings event-window guards.

Phase 1 stores events in memory. Phase 2 will populate from FRED release schedule
+ a static earnings calendar.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum


class EventKind(str, Enum):
    FOMC = "fomc"
    CPI = "cpi"
    NFP = "nfp"
    EARNINGS = "earnings"


@dataclass(frozen=True)
class EconomicEvent:
    kind: EventKind
    date: dt.date
    symbols: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        # Allow set or frozenset on input; normalize to frozenset.
        if not isinstance(self.symbols, frozenset):
            object.__setattr__(self, "symbols", frozenset(self.symbols))


@dataclass
class EventCalendar:
    events: list[EconomicEvent]

    def events_in_window(self, start: dt.date, days: int) -> list[EconomicEvent]:
        end = start + dt.timedelta(days=days)
        return [e for e in self.events if start <= e.date <= end]

    def symbol_in_event_window(self, symbol: str, start: dt.date, days: int) -> bool:
        for e in self.events_in_window(start, days):
            if symbol in e.symbols:
                return True
        return False
```

- [ ] **Step 9.4: Run tests to verify pass**

Run: `uv run pytest tests/test_calendars_events.py -v`
Expected: 5 passed.

- [ ] **Step 9.5: Commit**

```bash
git add src/trading_assistant/calendars/events.py tests/test_calendars_events.py
git commit -m "feat(calendars): add in-memory event calendar for event-window guards"
```

---

## Task 10: Market data client

**Files:**
- Create: `src/trading_assistant/ingest/__init__.py`
- Create: `src/trading_assistant/ingest/market_data.py`
- Test: `tests/test_ingest_market_data.py`

The client takes injected fetchers (Alpaca + yfinance), returns a normalized `Quote` dataclass, and falls back gracefully.

- [ ] **Step 10.1: Write the failing test**

Create `tests/test_ingest_market_data.py`:
```python
import pytest

from trading_assistant.ingest.market_data import (
    DataSourceFailure,
    MarketDataClient,
    Quote,
)


class FakeAlpaca:
    def __init__(self, quotes: dict[str, Quote] | None = None, raise_exc: bool = False):
        self._quotes = quotes or {}
        self._raise = raise_exc

    def latest_quote(self, symbol: str) -> Quote:
        if self._raise:
            raise RuntimeError("alpaca down")
        if symbol not in self._quotes:
            raise KeyError(symbol)
        return self._quotes[symbol]


class FakeYahoo:
    def __init__(self, quotes: dict[str, Quote] | None = None, raise_exc: bool = False):
        self._quotes = quotes or {}
        self._raise = raise_exc

    def latest_quote(self, symbol: str) -> Quote:
        if self._raise:
            raise RuntimeError("yahoo down")
        if symbol not in self._quotes:
            raise KeyError(symbol)
        return self._quotes[symbol]


def quote(sym: str, bid: float, ask: float, last: float) -> Quote:
    return Quote(
        symbol=sym, bid=bid, ask=ask, last=last,
        ts="2026-04-27T14:30:00Z", source="test",
    )


def test_uses_primary_when_healthy():
    primary = FakeAlpaca({"SPY": quote("SPY", 470.0, 470.05, 470.02)})
    fallback = FakeYahoo()
    client = MarketDataClient(primary=primary, fallback=fallback)
    q = client.snapshot(["SPY"])["SPY"]
    assert q.bid == 470.0
    assert q.source == "test"


def test_falls_back_when_primary_raises():
    primary = FakeAlpaca(raise_exc=True)
    fallback = FakeYahoo({"SPY": quote("SPY", 470.0, 470.05, 470.02)})
    client = MarketDataClient(primary=primary, fallback=fallback)
    q = client.snapshot(["SPY"])["SPY"]
    assert q.symbol == "SPY"


def test_raises_when_both_sources_fail():
    primary = FakeAlpaca(raise_exc=True)
    fallback = FakeYahoo(raise_exc=True)
    client = MarketDataClient(primary=primary, fallback=fallback)
    with pytest.raises(DataSourceFailure):
        client.snapshot(["SPY"])


def test_snapshot_supports_multiple_symbols():
    primary = FakeAlpaca({
        "SPY": quote("SPY", 470, 470.05, 470.02),
        "QQQ": quote("QQQ", 380, 380.04, 380.01),
    })
    fallback = FakeYahoo()
    client = MarketDataClient(primary=primary, fallback=fallback)
    snap = client.snapshot(["SPY", "QQQ"])
    assert set(snap.keys()) == {"SPY", "QQQ"}
```

- [ ] **Step 10.2: Run test to verify it fails**

Run: `uv run pytest tests/test_ingest_market_data.py -v`
Expected: FAIL with import error.

- [ ] **Step 10.3: Implement `ingest/market_data.py`**

Create `src/trading_assistant/ingest/__init__.py`:
```python
"""Data ingestion clients."""
```

Create `src/trading_assistant/ingest/market_data.py`:
```python
"""Market data client with Alpaca primary + Yahoo fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import structlog

log = structlog.get_logger(__name__)


class DataSourceFailure(Exception):
    """Both primary and fallback data sources failed."""


@dataclass(frozen=True)
class Quote:
    symbol: str
    bid: float
    ask: float
    last: float
    ts: str
    source: str


class _QuoteSource(Protocol):
    def latest_quote(self, symbol: str) -> Quote: ...


class MarketDataClient:
    def __init__(self, *, primary: _QuoteSource, fallback: _QuoteSource) -> None:
        self._primary = primary
        self._fallback = fallback

    def snapshot(self, symbols: list[str]) -> dict[str, Quote]:
        out: dict[str, Quote] = {}
        for sym in symbols:
            try:
                out[sym] = self._primary.latest_quote(sym)
                continue
            except Exception as exc:  # noqa: BLE001
                log.warning("primary_quote_failed", symbol=sym, error=str(exc))
            try:
                out[sym] = self._fallback.latest_quote(sym)
            except Exception as exc:  # noqa: BLE001
                log.error("fallback_quote_failed", symbol=sym, error=str(exc))
                raise DataSourceFailure(f"both sources failed for {sym}") from exc
        return out
```

- [ ] **Step 10.4: Run tests to verify pass**

Run: `uv run pytest tests/test_ingest_market_data.py -v`
Expected: 4 passed.

- [ ] **Step 10.5: Commit**

```bash
git add src/trading_assistant/ingest tests/test_ingest_market_data.py
git commit -m "feat(ingest): add MarketDataClient with primary/fallback quote sources"
```

---

## Task 11: Options chain client

**Files:**
- Create: `src/trading_assistant/ingest/options_chain.py`
- Test: `tests/test_ingest_options_chain.py`

Same pattern: injected primary + fallback, normalized output. The `OptionContract` dataclass keeps the contract identifier in OCC format (`SPY230721C00450000` style).

- [ ] **Step 11.1: Write the failing test**

Create `tests/test_ingest_options_chain.py`:
```python
import datetime as dt

import pytest

from trading_assistant.ingest.options_chain import (
    DataSourceFailure,
    OptionContract,
    OptionsChainClient,
)


def contract(occ: str, bid: float, ask: float) -> OptionContract:
    return OptionContract(
        occ_symbol=occ,
        underlying="SPY",
        expiry=dt.date(2026, 5, 15),
        strike=470.0,
        right="C",
        bid=bid,
        ask=ask,
        last=(bid + ask) / 2,
        iv=0.18,
    )


class FakeYahoo:
    def __init__(self, chains=None, raise_exc=False):
        self._chains = chains or {}
        self._raise = raise_exc

    def chain(self, symbol: str) -> list[OptionContract]:
        if self._raise:
            raise RuntimeError("yahoo down")
        return self._chains.get(symbol, [])


class FakeAlpaca:
    def __init__(self, chains=None, raise_exc=False):
        self._chains = chains or {}
        self._raise = raise_exc

    def chain(self, symbol: str) -> list[OptionContract]:
        if self._raise:
            raise RuntimeError("alpaca down")
        return self._chains.get(symbol, [])


def test_returns_chain_from_primary():
    primary = FakeYahoo({"SPY": [contract("SPY...", 1.0, 1.1)]})
    fallback = FakeAlpaca()
    client = OptionsChainClient(primary=primary, fallback=fallback)
    chain = client.chain("SPY")
    assert len(chain) == 1
    assert chain[0].underlying == "SPY"


def test_falls_back_when_primary_raises():
    primary = FakeYahoo(raise_exc=True)
    fallback = FakeAlpaca({"SPY": [contract("SPY...", 1.0, 1.1)]})
    client = OptionsChainClient(primary=primary, fallback=fallback)
    chain = client.chain("SPY")
    assert len(chain) == 1


def test_raises_when_both_sources_fail():
    primary = FakeYahoo(raise_exc=True)
    fallback = FakeAlpaca(raise_exc=True)
    client = OptionsChainClient(primary=primary, fallback=fallback)
    with pytest.raises(DataSourceFailure):
        client.chain("SPY")


def test_returns_empty_chain_without_falling_back():
    """An empty chain is a *valid* answer, not a failure."""
    primary = FakeYahoo({"SPY": []})
    fallback = FakeAlpaca({"SPY": [contract("SPY...", 1.0, 1.1)]})
    client = OptionsChainClient(primary=primary, fallback=fallback)
    chain = client.chain("SPY")
    assert chain == []
```

- [ ] **Step 11.2: Run test to verify it fails**

Run: `uv run pytest tests/test_ingest_options_chain.py -v`
Expected: FAIL with import error.

- [ ] **Step 11.3: Implement `ingest/options_chain.py`**

Create `src/trading_assistant/ingest/options_chain.py`:
```python
"""Options chain client with yfinance primary + Alpaca fallback."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal, Protocol

import structlog

log = structlog.get_logger(__name__)


class DataSourceFailure(Exception):
    """Both primary and fallback options-chain sources failed."""


@dataclass(frozen=True)
class OptionContract:
    occ_symbol: str
    underlying: str
    expiry: dt.date
    strike: float
    right: Literal["C", "P"]
    bid: float
    ask: float
    last: float
    iv: float | None


class _ChainSource(Protocol):
    def chain(self, symbol: str) -> list[OptionContract]: ...


class OptionsChainClient:
    def __init__(self, *, primary: _ChainSource, fallback: _ChainSource) -> None:
        self._primary = primary
        self._fallback = fallback

    def chain(self, symbol: str) -> list[OptionContract]:
        try:
            return self._primary.chain(symbol)
        except Exception as exc:  # noqa: BLE001
            log.warning("primary_chain_failed", symbol=symbol, error=str(exc))
        try:
            return self._fallback.chain(symbol)
        except Exception as exc:  # noqa: BLE001
            log.error("fallback_chain_failed", symbol=symbol, error=str(exc))
            raise DataSourceFailure(f"both chain sources failed for {symbol}") from exc
```

- [ ] **Step 11.4: Run tests to verify pass**

Run: `uv run pytest tests/test_ingest_options_chain.py -v`
Expected: 4 passed.

- [ ] **Step 11.5: Commit**

```bash
git add src/trading_assistant/ingest/options_chain.py tests/test_ingest_options_chain.py
git commit -m "feat(ingest): add OptionsChainClient with primary/fallback chain sources"
```

---

## Task 12: Economic data client (FRED)

**Files:**
- Create: `src/trading_assistant/ingest/economic.py`
- Test: `tests/test_ingest_economic.py`

The client wraps an injectable "FRED gateway" so tests don't hit the network. Phase 1 fetches the latest observation for a fixed list of series (CPI, NFP, Fed funds rate). Persists to `econ_observations`.

- [ ] **Step 12.1: Write the failing test**

Create `tests/test_ingest_economic.py`:
```python
import datetime as dt

import pytest

from trading_assistant.db.repositories import (
    AppStateRepo,  # noqa: F401  (ensure import path stable)
)
from trading_assistant.db.schema import create_schema
from trading_assistant.ingest.economic import (
    DEFAULT_SERIES,
    EconomicDataClient,
    EconObservation,
)


class FakeFredGateway:
    def __init__(self, latest: dict[str, EconObservation]):
        self._latest = latest

    def latest(self, series_id: str) -> EconObservation:
        if series_id not in self._latest:
            raise KeyError(series_id)
        return self._latest[series_id]


@pytest.fixture
def conn(db_conn):
    create_schema(db_conn)
    return db_conn


def test_refresh_persists_observations(conn):
    gw = FakeFredGateway({
        "CPIAUCSL": EconObservation("CPIAUCSL", dt.date(2026, 4, 10), 320.5),
        "PAYEMS":   EconObservation("PAYEMS",   dt.date(2026, 4, 5),  158_000.0),
        "DFF":      EconObservation("DFF",      dt.date(2026, 4, 25), 4.25),
    })
    client = EconomicDataClient(gateway=gw, conn=conn)
    client.refresh()
    rows = list(conn.execute("SELECT series_id, value FROM econ_observations ORDER BY series_id"))
    assert {r["series_id"] for r in rows} == set(DEFAULT_SERIES)


def test_refresh_skips_failed_series(conn):
    gw = FakeFredGateway({
        "CPIAUCSL": EconObservation("CPIAUCSL", dt.date(2026, 4, 10), 320.5),
        # PAYEMS missing → should be skipped, not crash
        "DFF":      EconObservation("DFF",      dt.date(2026, 4, 25), 4.25),
    })
    client = EconomicDataClient(gateway=gw, conn=conn)
    client.refresh()
    rows = list(conn.execute("SELECT series_id FROM econ_observations"))
    fetched = {r["series_id"] for r in rows}
    assert "PAYEMS" not in fetched
    assert "CPIAUCSL" in fetched
    assert "DFF" in fetched


def test_refresh_is_idempotent(conn):
    gw = FakeFredGateway({
        "CPIAUCSL": EconObservation("CPIAUCSL", dt.date(2026, 4, 10), 320.5),
        "PAYEMS":   EconObservation("PAYEMS",   dt.date(2026, 4, 5),  158_000.0),
        "DFF":      EconObservation("DFF",      dt.date(2026, 4, 25), 4.25),
    })
    client = EconomicDataClient(gateway=gw, conn=conn)
    client.refresh()
    client.refresh()
    rows = list(conn.execute("SELECT COUNT(*) AS n FROM econ_observations"))
    assert rows[0]["n"] == 3
```

- [ ] **Step 12.2: Run test to verify it fails**

Run: `uv run pytest tests/test_ingest_economic.py -v`
Expected: FAIL with import error.

- [ ] **Step 12.3: Implement `ingest/economic.py`**

Create `src/trading_assistant/ingest/economic.py`:
```python
"""Economic data client using FRED for CPI / NFP / Fed funds rate."""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass
from typing import Protocol

import structlog

log = structlog.get_logger(__name__)

DEFAULT_SERIES: tuple[str, ...] = ("CPIAUCSL", "PAYEMS", "DFF")


@dataclass(frozen=True)
class EconObservation:
    series_id: str
    observation_date: dt.date
    value: float


class _FredGateway(Protocol):
    def latest(self, series_id: str) -> EconObservation: ...


class EconomicDataClient:
    def __init__(
        self,
        *,
        gateway: _FredGateway,
        conn: sqlite3.Connection,
        series: tuple[str, ...] = DEFAULT_SERIES,
    ) -> None:
        self._gw = gateway
        self._conn = conn
        self._series = series

    def refresh(self) -> None:
        now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
        for sid in self._series:
            try:
                obs = self._gw.latest(sid)
            except Exception as exc:  # noqa: BLE001
                log.warning("fred_fetch_failed", series=sid, error=str(exc))
                continue
            self._conn.execute(
                "INSERT INTO econ_observations(series_id, observation_date, value, fetched_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(series_id, observation_date) DO UPDATE SET "
                "value=excluded.value, fetched_at=excluded.fetched_at",
                (obs.series_id, obs.observation_date.isoformat(), obs.value, now_iso),
            )
```

- [ ] **Step 12.4: Run tests to verify pass**

Run: `uv run pytest tests/test_ingest_economic.py -v`
Expected: 3 passed.

- [ ] **Step 12.5: Commit**

```bash
git add src/trading_assistant/ingest/economic.py tests/test_ingest_economic.py
git commit -m "feat(ingest): add EconomicDataClient with FRED gateway and persistence"
```

---

## Task 13: News client (RSS + Finnhub)

**Files:**
- Create: `src/trading_assistant/ingest/news.py`
- Test: `tests/test_ingest_news.py`

Two sources:
1. RSS via `feedparser` — accepts a list of feed URLs, parses entries, computes `url_hash`, persists.
2. Finnhub via `httpx` for general market news headlines (free tier).

Both produce a normalized `NewsItem` dataclass. Dedup happens at the repo layer via `INSERT OR IGNORE` on `url_hash`.

- [ ] **Step 13.1: Write the failing test**

Create `tests/test_ingest_news.py`:
```python
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
```

- [ ] **Step 13.2: Run test to verify it fails**

Run: `uv run pytest tests/test_ingest_news.py -v`
Expected: FAIL with import error.

- [ ] **Step 13.3: Implement `ingest/news.py`**

Create `src/trading_assistant/ingest/news.py`:
```python
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
```

- [ ] **Step 13.4: Run tests to verify pass**

Run: `uv run pytest tests/test_ingest_news.py -v`
Expected: 4 passed.

- [ ] **Step 13.5: Commit**

```bash
git add src/trading_assistant/ingest/news.py tests/test_ingest_news.py
git commit -m "feat(ingest): add NewsClient with RSS + Finnhub gateways and dedup"
```

---

## Task 14: CLI snapshot command

**Files:**
- Create: `src/trading_assistant/__main__.py`
- Create: `src/trading_assistant/cli.py`
- Test: `tests/test_cli_snapshot.py`

The snapshot command:
1. Loads config + secrets
2. Configures logging
3. Opens DB and creates schema (idempotent)
4. Builds clients (with thin Alpaca/yfinance/FRED wrappers — see step 14.3 for the wrapper pattern)
5. Calls market data + news + econ ingestion
6. Prints a human-readable summary

Phase 1 deliberately stops at "ingest and print." Signal generation is Phase 2.

- [ ] **Step 14.1: Write the failing test**

Create `tests/test_cli_snapshot.py`:
```python
from typer.testing import CliRunner

from trading_assistant.cli import app


def test_help_lists_snapshot_command():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "snapshot" in result.stdout


def test_snapshot_requires_config_path():
    runner = CliRunner()
    result = runner.invoke(app, ["snapshot"])
    # Missing --config should print error and exit non-zero (Typer default).
    assert result.exit_code != 0
```

- [ ] **Step 14.2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_snapshot.py -v`
Expected: FAIL with import error.

- [ ] **Step 14.3: Implement the CLI**

Create `src/trading_assistant/__main__.py`:
```python
from trading_assistant.cli import app

if __name__ == "__main__":
    app()
```

Create `src/trading_assistant/cli.py`:
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

    # Wrappers wiring lives below. Each external dependency is created here
    # rather than at import time so tests can substitute fakes if/when needed.
    from trading_assistant.ingest.economic import EconomicDataClient
    from trading_assistant.ingest.market_data import MarketDataClient
    from trading_assistant.ingest.news import FinnhubGateway, NewsClient, RSSGateway
    from trading_assistant.ingest.options_chain import OptionsChainClient

    import feedparser
    import httpx

    from trading_assistant.adapters.alpaca import AlpacaQuoteAdapter, AlpacaChainAdapter
    from trading_assistant.adapters.yahoo import YahooQuoteAdapter, YahooChainAdapter
    from trading_assistant.adapters.fred import FredAdapter

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
```

- [ ] **Step 14.4: Add adapter stubs**

The CLI imports thin adapters. We create minimal real adapters now; they implement the `Quote`/`OptionContract`/`EconObservation` protocols expected by the clients. **Their tests are deferred to Task 15.**

Create `src/trading_assistant/adapters/__init__.py`:
```python
"""Thin adapters bridging external SDKs to internal protocols."""
```

Create `src/trading_assistant/adapters/alpaca.py`:
```python
"""Alpaca SDK adapters for quote and chain protocols."""

from __future__ import annotations

import datetime as dt

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

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
            ts=q.timestamp.isoformat() if q.timestamp else dt.datetime.utcnow().isoformat(),
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
```

Create `src/trading_assistant/adapters/yahoo.py`:
```python
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
```

Create `src/trading_assistant/adapters/fred.py`:
```python
"""FRED adapter."""

from __future__ import annotations

import datetime as dt

from fredapi import Fred

from trading_assistant.ingest.economic import EconObservation


class FredAdapter:
    def __init__(self, *, api_key: str) -> None:
        self._client = Fred(api_key=api_key)

    def latest(self, series_id: str) -> EconObservation:
        series = self._client.get_series_latest_release(series_id)
        last_index = series.index[-1]
        last_value = series.iloc[-1]
        return EconObservation(
            series_id=series_id,
            observation_date=last_index.date() if hasattr(last_index, "date") else dt.date.today(),
            value=float(last_value),
        )
```

- [ ] **Step 14.5: Run tests to verify pass**

Run: `uv run pytest tests/test_cli_snapshot.py -v`
Expected: 2 passed.

- [ ] **Step 14.6: Run the full test suite**

Run: `uv run pytest -v`
Expected: All tests pass (~38 tests).

- [ ] **Step 14.7: Commit**

```bash
git add src/trading_assistant/__main__.py src/trading_assistant/cli.py src/trading_assistant/adapters tests/test_cli_snapshot.py
git commit -m "feat(cli): add snapshot command + Alpaca/Yahoo/FRED adapters"
```

---

## Task 15: End-to-end smoke against real APIs (manual)

This is the only manual step in the plan; everything else is automated tests. The point is to verify the credentials and adapters work against live free APIs before declaring Phase 1 done.

- [ ] **Step 15.1: Set up secrets**

Run:
```bash
mkdir -p ~/.config/trading-assistant
cp .env.example ~/.config/trading-assistant/.env
cp config.yaml.example ~/.config/trading-assistant/config.yaml
chmod 600 ~/.config/trading-assistant/.env
```

Open `~/.config/trading-assistant/.env` and fill in:
- `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` — sign up at https://app.alpaca.markets/signup, generate a paper-trading key pair from the dashboard
- `FRED_API_KEY` — sign up at https://fred.stlouisfed.org/docs/api/api_key.html
- `FINNHUB_API_KEY` — sign up at https://finnhub.io/register
- `ANTHROPIC_API_KEY` — at console.anthropic.com (any working key, used in Phase 2)
- `PUSHOVER_USER_KEY` / `PUSHOVER_APP_TOKEN` — at https://pushover.net (used in Phase 4)

- [ ] **Step 15.2: Run the snapshot command**

Run:
```bash
uv run trading-assistant snapshot \
  --config ~/.config/trading-assistant/config.yaml \
  --env ~/.config/trading-assistant/.env \
  --db ./data/app.db
```

Expected output:
- A `=== Snapshot ===` block listing quotes for SPY/QQQ/IWM/DIA, chain counts (likely > 0 from Yahoo), a news count > 0, and "Econ data refreshed."
- No tracebacks.

- [ ] **Step 15.3: Verify SQLite contents**

Run: `sqlite3 ./data/app.db "SELECT COUNT(*) FROM news_items; SELECT COUNT(*) FROM econ_observations;"`
Expected: Both counts > 0.

- [ ] **Step 15.4: Re-run snapshot to confirm idempotence**

Run the same `trading-assistant snapshot` command again.
Expected: Runs cleanly. News dedup means new-news count may be 0 on the second run.

- [ ] **Step 15.5: No commit needed**

This task verifies behavior; no code changes.

---

## Phase 1 acceptance criteria

When all tasks complete:

- [ ] `uv run pytest -v` passes with all tests green (~38 tests).
- [ ] `uv run trading-assistant snapshot --help` shows usage.
- [ ] Running `snapshot` against real free APIs prints quotes for SPY/QQQ/IWM/DIA, refreshes econ data, dedupes news.
- [ ] SQLite database exists with WAL mode, all tables present, audit_log writable, news + econ persisted.
- [ ] No secrets appear in any log line or error message.
- [ ] `git log --oneline` shows ~14 focused commits, one per task.

---

## Self-review (already performed)

- ✅ **Spec coverage:** Foundation scope per Phase 1 in spec section 5: data ingestion clients ✅, market calendar ✅, event calendar (skeleton) ✅, audit log ✅, secrets handling ✅, mode flag ✅. SignalGenerators / IdeaSynthesizer / Validator / Executor / Notifier / Web / Scheduler / Backtest are explicitly Phase 2-5.
- ✅ **Placeholders:** None. All steps include actual code or commands. `AlpacaChainAdapter` is intentionally a stub (returns `[]`) because the spec marks Alpaca options data tier as YELLOW pending verification — this is documented in the adapter docstring, not hidden.
- ✅ **Type consistency:** `Quote`, `OptionContract`, `EconObservation`, `NewsItem`, `EconomicEvent`, `EventKind` are defined once and referenced consistently. Repo method names (`upsert`, `fresh_since`, `acquire`, `set`, `get`, `write`) are consistent across tasks.
