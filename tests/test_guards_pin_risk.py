"""PinRiskGuard tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.guards.pin_risk import PinRiskGuard
from trading_assistant.brain.validator import GuardOutcome
from trading_assistant.ingest.market_data import Quote
from trading_assistant.intents.model import Leg, Strategy, TradeIntent


class _FakeQuotes:
    def __init__(self, mids: dict[str, float]) -> None:
        self._mids = mids

    def snapshot(self, symbols: list[str]) -> dict[str, Quote]:
        return {s: Quote(symbol=s, bid=self._mids[s] - 0.05, ask=self._mids[s] + 0.05,
                          last=self._mids[s], ts=dt.datetime.now(dt.timezone.utc),
                          source="fake")
                for s in symbols if s in self._mids}


def _spread_intent(strike_long: float, strike_short: float, days_to_exp: int) -> TradeIntent:
    expiry = dt.date(2026, 5, 11) + dt.timedelta(days=days_to_exp)
    return TradeIntent(
        id="i", created_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
        signal_ids=["s"], symbol="SPY", strategy=Strategy.BULL_CALL_SPREAD,
        legs=[
            Leg(side="buy", right="C", strike=strike_long, expiry=expiry, qty=1),
            Leg(side="sell", right="C", strike=strike_short, expiry=expiry, qty=1),
        ],
        rationale_md="x", max_loss_usd=100.0, max_gain_usd=200.0, confidence=0.5,
    )


def test_accepts_when_expiry_outside_7_day_window():
    guard = PinRiskGuard(quote_client=_FakeQuotes({"SPY": 740.0}),
                          pin_pct=0.015, now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    intent = _spread_intent(strike_long=740.0, strike_short=740.5, days_to_exp=14)
    assert guard.check(intent).outcome == GuardOutcome.ACCEPT


def test_rejects_when_short_strike_within_pin_band_at_expiry_under_7_days():
    guard = PinRiskGuard(quote_client=_FakeQuotes({"SPY": 740.0}),
                          pin_pct=0.015, now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    # 740 mid, 1.5% band = ±$11.10; short strike at 741 is within band.
    intent = _spread_intent(strike_long=738.0, strike_short=741.0, days_to_exp=5)
    res = guard.check(intent)
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "pin_risk"


def test_accepts_when_short_strike_outside_pin_band():
    guard = PinRiskGuard(quote_client=_FakeQuotes({"SPY": 740.0}),
                          pin_pct=0.015, now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    # 740 mid, 1.5% band = ±$11.10; short strike at 760 is outside band.
    intent = _spread_intent(strike_long=755.0, strike_short=760.0, days_to_exp=5)
    assert guard.check(intent).outcome == GuardOutcome.ACCEPT


def test_long_only_intent_has_no_pin_risk():
    """LONG_CALL has no short leg, so pin risk doesn't apply."""
    guard = PinRiskGuard(quote_client=_FakeQuotes({"SPY": 740.0}),
                          pin_pct=0.015, now=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc))
    intent = TradeIntent(
        id="i", created_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
        signal_ids=["s"], symbol="SPY", strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=740.0,
                   expiry=dt.date(2026, 5, 14), qty=1)],
        rationale_md="x", max_loss_usd=100.0, max_gain_usd=None, confidence=0.5,
    )
    assert guard.check(intent).outcome == GuardOutcome.ACCEPT
