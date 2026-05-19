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
