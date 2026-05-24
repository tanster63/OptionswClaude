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
- Expiry: 14-45 calendar days out for swing positioning.
- max_loss_usd reflects total risk per contract (premium paid for long, max spread loss for spreads).
- confidence in [0.0, 1.0]. Be conservative - 0.5 is "modestly compelling."
- Return STRICT JSON ONLY. No prose, no markdown fences.
- Return {{"proposals": []}} when no setup is compelling.

OUTPUT SCHEMA (use these EXACT field names; do not substitute synonyms):

{{
  "proposals": [
    {{
      "symbol": "SPY",
      "strategy": "bull_call_spread",
      "legs": [
        {{"side": "buy",  "right": "C", "strike": 740.0, "expiry": "2026-06-19", "qty": 1}},
        {{"side": "sell", "right": "C", "strike": 745.0, "expiry": "2026-06-19", "qty": 1}}
      ],
      "rationale_md": "Markdown explanation citing signals.",
      "max_loss_usd": 250.0,
      "max_gain_usd": 250.0,
      "confidence": 0.55,
      "signal_ids": ["sig_id_1"]
    }}
  ]
}}

Field name rules (these MUST match exactly):
- Leg fields: side ("buy"|"sell"), right ("C"|"P"), strike (number), expiry ("YYYY-MM-DD"), qty (int >= 1)
- NEVER use: "action", "option_type", "quantity", "type" — use side/right/qty.
- Proposal-level: rationale_md (not "rationale"), max_gain_usd (not "target_profit_usd"; null if uncapped).
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
