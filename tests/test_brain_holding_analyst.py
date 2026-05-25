"""HoldingAnalyst tests."""

from __future__ import annotations

import datetime as dt
import json

from trading_assistant.brain.anthropic_client import LLMResponse
from trading_assistant.brain.holding_analyst import (
    HoldingAction,
    HoldingAnalyst,
    HoldingContext,
    HoldingRecommendation,
)
from trading_assistant.ingest.bars import Bar
from trading_assistant.ingest.market_data import Quote


class _FakeLLM:
    def __init__(self, text: str) -> None:
        self._text = text
        self.last_user: str | None = None
        self.last_system: str | None = None

    def complete(self, system: str, user: str) -> LLMResponse:
        self.last_user = user
        self.last_system = system
        return LLMResponse(text=self._text, input_tokens=100, output_tokens=50,
                           cache_read_tokens=0, cache_creation_tokens=0)


def _ctx(shares: float = 100, cost_basis: float = 25.0, account: str = "taxable") -> HoldingContext:
    return HoldingContext(
        symbol="OUST",
        shares=shares,
        cost_basis=cost_basis,
        account=account,
        current_quote=Quote(symbol="OUST", bid=36.95, ask=37.05, last=37.00,
                            ts=dt.datetime.now(dt.timezone.utc).isoformat(), source="yahoo"),
        bars_90d=[Bar(symbol="OUST", ts=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
                       open=30.0, high=31.0, low=29.0, close=30.0, volume=100000)] * 60,
        iv_summary={"median_atm_iv": 1.15, "regime": "high"},
        recent_news=[{"title": "OUST wins big lidar contract", "source": "test"}],
    )


def test_analyze_returns_recommendation_on_valid_llm_response():
    payload = {
        "action": "trim",
        "confidence": 0.65,
        "rationale_md": "Up 48% from cost basis; consider trimming half.",
        "key_risks": ["high IV could deflate", "small cap volatility"],
        "tax_note": "Position held <1yr; trim would be short-term gain.",
    }
    llm = _FakeLLM(json.dumps(payload))
    analyst = HoldingAnalyst(llm=llm)
    rec = analyst.analyze(_ctx())
    assert rec is not None
    assert rec.action == HoldingAction.TRIM
    assert rec.confidence == 0.65
    assert "Up 48%" in rec.rationale_md
    assert len(rec.key_risks) == 2
    assert rec.tax_note is not None


def test_analyze_returns_none_on_unparseable_llm_response():
    analyst = HoldingAnalyst(llm=_FakeLLM("not json"))
    assert analyst.analyze(_ctx()) is None


def test_analyze_handles_text_wrapped_json():
    payload = {"action": "hold", "confidence": 0.7,
               "rationale_md": "x", "key_risks": [], "tax_note": None}
    wrapped = f"Here's my analysis:\n```json\n{json.dumps(payload)}\n```\nDone."
    rec = HoldingAnalyst(llm=_FakeLLM(wrapped)).analyze(_ctx())
    assert rec is not None
    assert rec.action == HoldingAction.HOLD


def test_analyze_supports_zero_shares_as_considering_purchase():
    payload = {"action": "buy_more", "confidence": 0.5,
               "rationale_md": "Establish small position", "key_risks": ["vol"], "tax_note": None}
    rec = HoldingAnalyst(llm=_FakeLLM(json.dumps(payload))).analyze(_ctx(shares=0.0))
    assert rec is not None
    assert rec.action == HoldingAction.BUY_MORE


def test_analyze_passes_position_state_to_llm():
    """The user payload sent to the LLM must include unrealized P&L math."""
    llm = _FakeLLM(json.dumps({"action": "hold", "confidence": 0.5,
                                "rationale_md": "x", "key_risks": [], "tax_note": None}))
    analyst = HoldingAnalyst(llm=llm)
    analyst.analyze(_ctx(shares=100, cost_basis=25.0))
    user_payload = json.loads(llm.last_user)
    assert "position_state" in user_payload
    # Mid quote is 37.00; cost basis 25.0; so unrealized PnL/share = 12.0
    assert user_payload["position_state"]["unrealized_pnl_per_share"] == 12.0
    assert user_payload["position_state"]["unrealized_pnl_total"] == 1200.0
    assert user_payload["position_state"]["unrealized_pnl_pct"] == 48.0


def test_analyze_drops_tax_note_when_account_is_roth():
    """For roth/ira accounts the LLM should be told taxes don't matter."""
    payload = {"action": "hold", "confidence": 0.5,
               "rationale_md": "x", "key_risks": [], "tax_note": None}
    llm = _FakeLLM(json.dumps(payload))
    analyst = HoldingAnalyst(llm=llm)
    analyst.analyze(_ctx(account="roth"))
    assert "roth" in llm.last_user.lower() or "ira" in llm.last_user.lower()
