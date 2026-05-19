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
