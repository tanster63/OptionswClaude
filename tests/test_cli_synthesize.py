"""CLI synthesize command smoke test (with all externals mocked)."""

from __future__ import annotations

import datetime as dt

from typer.testing import CliRunner

from trading_assistant.cli import _print_synthesis_results, app
from trading_assistant.intents.model import Leg, Strategy, TradeIntent


def test_cli_help_lists_synthesize_command():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "synthesize" in result.stdout
    assert "snapshot" in result.stdout


_NOW = dt.datetime(2026, 5, 26, 14, 30, tzinfo=dt.timezone.utc)
_EXP = dt.date(2026, 6, 19)


def _legs_for(strategy: Strategy) -> list[Leg]:
    if strategy == Strategy.LONG_CALL:
        return [Leg(side="buy", right="C", strike=740.0, expiry=_EXP, qty=1)]
    if strategy == Strategy.LONG_PUT:
        return [Leg(side="buy", right="P", strike=740.0, expiry=_EXP, qty=1)]
    if strategy == Strategy.BULL_CALL_SPREAD:
        return [
            Leg(side="buy", right="C", strike=740.0, expiry=_EXP, qty=1),
            Leg(side="sell", right="C", strike=745.0, expiry=_EXP, qty=1),
        ]
    if strategy == Strategy.BEAR_PUT_SPREAD:
        return [
            Leg(side="buy", right="P", strike=745.0, expiry=_EXP, qty=1),
            Leg(side="sell", right="P", strike=740.0, expiry=_EXP, qty=1),
        ]
    raise ValueError(f"unknown strategy: {strategy}")


def _intent(symbol: str = "SPY", strategy: Strategy = Strategy.LONG_CALL,
             max_loss: float = 200.0, max_gain: float | None = None,
             confidence: float = 0.55) -> TradeIntent:
    return TradeIntent(
        id=f"i_{symbol}_{strategy.value}", created_at=_NOW, signal_ids=["s"],
        symbol=symbol, strategy=strategy,
        legs=_legs_for(strategy),
        rationale_md="thesis", max_loss_usd=max_loss, max_gain_usd=max_gain,
        confidence=confidence,
    )


def _capture():
    out: list[str] = []
    return out, out.append


def test_prints_accepted_idea_block():
    out, sink = _capture()
    _print_synthesis_results(
        now=_NOW, session_label="OPEN", session_warning=None,
        all_signals_count=5, candidates_count=1,
        accepted=[_intent()], rejected=[],
        echo=sink,
    )
    text = "\n".join(out)
    assert "Accepted:   1" in text
    assert "SPY  long_call" in text
    assert "Rationale:" in text
    # No "Rejected ideas" block when nothing was rejected
    assert "--- Rejected ideas ---" not in text


def test_prints_rejected_block_with_reasons():
    out, sink = _capture()
    _print_synthesis_results(
        now=_NOW, session_label="OPEN", session_warning=None,
        all_signals_count=5, candidates_count=2,
        accepted=[],
        rejected=[(_intent("QQQ", Strategy.BULL_CALL_SPREAD), "spread_too_wide"),
                  (_intent("IWM", Strategy.LONG_PUT), "risk_reward_too_low")],
        echo=sink,
    )
    text = "\n".join(out)
    assert "--- Rejected ideas ---" in text
    assert "QQQ" in text and "spread_too_wide" in text
    assert "IWM" in text and "risk_reward_too_low" in text


def test_no_trade_summary_when_zero_signals():
    out, sink = _capture()
    _print_synthesis_results(
        now=_NOW, session_label="CLOSED",
        session_warning="⚠️  Market closed",
        all_signals_count=0, candidates_count=0,
        accepted=[], rejected=[], echo=sink,
    )
    text = "\n".join(out)
    assert "No trades surfaced" in text
    assert "no signals were generated" in text


def test_no_trade_summary_when_signals_but_no_candidates():
    out, sink = _capture()
    _print_synthesis_results(
        now=_NOW, session_label="OPEN", session_warning=None,
        all_signals_count=6, candidates_count=0,
        accepted=[], rejected=[], echo=sink,
    )
    text = "\n".join(out)
    assert "No trades surfaced" in text
    assert "Claude declined" in text


def test_no_trade_summary_with_rejection_breakdown():
    out, sink = _capture()
    _print_synthesis_results(
        now=_NOW, session_label="OPEN", session_warning=None,
        all_signals_count=8, candidates_count=3,
        accepted=[],
        rejected=[(_intent("SPY"), "spread_too_wide"),
                  (_intent("QQQ"), "spread_too_wide"),
                  (_intent("IWM"), "risk_reward_too_low")],
        echo=sink,
    )
    text = "\n".join(out)
    assert "No trades surfaced" in text
    assert "Rejection breakdown:" in text
    assert "2x spread_too_wide" in text
    assert "1x risk_reward_too_low" in text


def test_session_warning_printed_when_closed():
    out, sink = _capture()
    _print_synthesis_results(
        now=_NOW, session_label="CLOSED",
        session_warning="⚠️  Market closed — paper only",
        all_signals_count=2, candidates_count=0,
        accepted=[], rejected=[], echo=sink,
    )
    text = "\n".join(out)
    assert "Market closed" in text


def test_no_session_warning_when_open():
    out, sink = _capture()
    _print_synthesis_results(
        now=_NOW, session_label="OPEN", session_warning=None,
        all_signals_count=2, candidates_count=1,
        accepted=[_intent()], rejected=[], echo=sink,
    )
    text = "\n".join(out)
    assert "⚠️" not in text
