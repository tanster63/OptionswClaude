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
