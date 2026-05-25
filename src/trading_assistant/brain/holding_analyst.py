"""Holding analyst: given a position, recommends HOLD/TRIM/SELL/BUY_MORE."""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from enum import Enum
from math import log as math_log, sqrt
from typing import Protocol

import structlog
from pydantic import BaseModel, Field, ValidationError

from trading_assistant.brain.anthropic_client import LLMResponse
from trading_assistant.brain.synthesizer import _extract_json
from trading_assistant.ingest.bars import Bar
from trading_assistant.ingest.market_data import Quote

logger = structlog.get_logger(__name__)


class HoldingAction(str, Enum):
    HOLD = "hold"
    TRIM = "trim"
    SELL = "sell"
    BUY_MORE = "buy_more"


class HoldingRecommendation(BaseModel):
    symbol: str
    action: HoldingAction
    confidence: float = Field(ge=0.0, le=1.0)
    rationale_md: str
    key_risks: list[str]
    tax_note: str | None = None  # populated only when account != "roth" / "ira"


@dataclass(frozen=True)
class HoldingContext:
    symbol: str
    shares: float
    cost_basis: float          # price per share paid
    account: str               # "roth", "ira", "taxable", "unknown"
    current_quote: Quote
    bars_90d: list[Bar]        # for vol/range/trend math
    iv_summary: dict | None    # {"median_atm_iv": float, "regime": "low"|"normal"|"high"} or None if no chain
    recent_news: list[dict]    # [{"title": ..., "source": ..., "published_at": ...}]


_SYSTEM_PROMPT = """\
You are a portfolio analyst for an individual investor holding US-listed equities.
Given a current holding (or "considering buying" if shares=0) and recent market/news context,
recommend ONE of: hold, trim, sell, buy_more.

You are NOT a registered investment advisor. Frame your output as analysis to consider,
never as an instruction. The user makes the final decision.

Reasoning principles:
- Cite specific signals: price action, vol regime, recent news, position size, holding period.
- For taxable accounts: factor in short-term vs long-term capital gains thresholds (ST = held < 1yr,
  taxed as ordinary income; LT = held >= 1yr, taxed at lower LT cap gains rate). For Roth/IRA,
  taxes are irrelevant - don't mention them.
- Be conservative with SELL on a profitable position when only mild headwinds - TRIM lets the user
  reduce risk while keeping skin in the game.
- For losing positions in a taxable account, mention tax-loss harvesting if down materially.
- Acknowledge what you DON'T know (you can't see balance sheet, can't predict earnings).

OUTPUT SCHEMA (strict JSON, no prose around it):

{
  "action": "hold|trim|sell|buy_more",
  "confidence": 0.0,
  "rationale_md": "Multi-paragraph markdown reasoning citing specifics.",
  "key_risks": ["risk 1", "risk 2", "risk 3"],
  "tax_note": "Brief tax consideration string, or null for Roth/IRA accounts."
}
"""


class _LLM(Protocol):
    def complete(self, system: str, user: str) -> LLMResponse: ...


class HoldingAnalyst:
    def __init__(self, llm: _LLM) -> None:
        self._llm = llm

    def analyze(self, ctx: HoldingContext) -> HoldingRecommendation | None:
        """Returns None if the LLM call fails or response is unparseable."""
        user_payload = _build_user_payload(ctx)
        user = json.dumps(user_payload, default=str)

        try:
            resp = self._llm.complete(system=_SYSTEM_PROMPT, user=user)
        except Exception as exc:  # noqa: BLE001
            logger.warning("holding_analyst_llm_failed", error=str(exc))
            return None

        payload = _extract_json(resp.text)
        if payload is None:
            logger.warning("holding_analyst_unparseable_response", sample=resp.text[:200])
            return None

        try:
            return HoldingRecommendation(
                symbol=ctx.symbol,
                action=HoldingAction(payload["action"]),
                confidence=float(payload["confidence"]),
                rationale_md=str(payload["rationale_md"]),
                key_risks=list(payload.get("key_risks") or []),
                tax_note=payload.get("tax_note"),
            )
        except (KeyError, ValueError, ValidationError) as exc:
            logger.warning("holding_analyst_payload_invalid", error=str(exc), payload=payload)
            return None


def _build_user_payload(ctx: HoldingContext) -> dict:
    q = ctx.current_quote
    if q.bid > 0 and q.ask > 0:
        mid = (q.bid + q.ask) / 2.0
    else:
        mid = q.last

    closes = [b.close for b in ctx.bars_90d]
    last_30 = closes[-30:] if len(closes) >= 30 else closes
    last_90 = closes[-90:] if len(closes) >= 90 else closes

    latest_close = closes[-1] if closes else None
    range_30d = [min(last_30), max(last_30)] if last_30 else None
    range_90d = [min(last_90), max(last_90)] if last_90 else None
    avg_close_30d = (sum(last_30) / len(last_30)) if last_30 else None
    pct_vs_30d_avg = ((mid / avg_close_30d - 1.0) * 100.0) if avg_close_30d else None
    realized_vol = _realized_vol_annualized(last_30)

    if ctx.shares > 0 and ctx.cost_basis > 0:
        pnl_per_share = mid - ctx.cost_basis
        pnl_total = pnl_per_share * ctx.shares
        pnl_pct = (mid / ctx.cost_basis - 1.0) * 100.0
    else:
        pnl_per_share = None
        pnl_total = None
        pnl_pct = None

    return {
        "symbol": ctx.symbol,
        "shares": ctx.shares,
        "cost_basis_per_share": ctx.cost_basis,
        "account_type": ctx.account,
        "current_quote": {
            "bid": q.bid,
            "ask": q.ask,
            "last": q.last,
            "mid": mid,
        },
        "price_history": {
            "latest_close": latest_close,
            "range_30d": range_30d,
            "range_90d": range_90d,
            "avg_close_30d": avg_close_30d,
            "pct_vs_30d_avg": pct_vs_30d_avg,
            "realized_vol_30d_annualized": realized_vol,
        },
        "implied_volatility": ctx.iv_summary,
        "position_state": {
            "unrealized_pnl_per_share": pnl_per_share,
            "unrealized_pnl_total": pnl_total,
            "unrealized_pnl_pct": pnl_pct,
        },
        "recent_news": ctx.recent_news[:15],
    }


def _realized_vol_annualized(closes: list[float]) -> float | None:
    """Annualized realized vol from log returns of close prices. None if too few points."""
    if len(closes) < 2:
        return None
    rets: list[float] = []
    for prev, curr in zip(closes, closes[1:]):
        if prev <= 0 or curr <= 0:
            continue
        rets.append(math_log(curr / prev))
    if len(rets) < 2:
        return None
    try:
        sd = statistics.stdev(rets)
    except statistics.StatisticsError:
        return None
    return sd * sqrt(252.0)
