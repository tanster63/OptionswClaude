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
    min_option_volume: int = 50
    min_option_open_interest: int = 100
    min_risk_reward_ratio: float = 1.0
    payoff_tolerance_pct: float = 0.05
    payoff_tolerance_min_usd: float = 20.0
    min_dte: int = 14
    max_dte: int = 45
    quote_stale_seconds: int = 900   # 15 minutes
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
