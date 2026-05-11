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
        n = len(fields(self))
        return f"Secrets(<{n} fields REDACTED>)"


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
