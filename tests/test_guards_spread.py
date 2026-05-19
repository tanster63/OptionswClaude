"""SpreadGuard tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.guards.spread import SpreadGuard
from trading_assistant.brain.validator import GuardOutcome
from trading_assistant.ingest.options_chain import OptionContract
from trading_assistant.intents.model import Leg, Strategy, TradeIntent


class _FakeChains:
    def __init__(self, by_symbol: dict[str, list[OptionContract]]) -> None:
        self._chains = by_symbol

    def chain(self, symbol: str) -> list[OptionContract]:
        return self._chains.get(symbol, [])


def _intent(strike: float = 740.0) -> TradeIntent:
    return TradeIntent(
        id="i", created_at=dt.datetime(2026, 5, 11, tzinfo=dt.timezone.utc),
        signal_ids=["s"], symbol="SPY", strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=strike,
                   expiry=dt.date(2026, 6, 19), qty=1)],
        rationale_md="x", max_loss_usd=200.0, max_gain_usd=None, confidence=0.5,
    )


def _contract(strike: float, bid: float, ask: float) -> OptionContract:
    return OptionContract(
        occ_symbol=f"X{strike}", underlying="SPY",
        expiry=dt.date(2026, 6, 19), strike=strike, right="C",
        bid=bid, ask=ask, last=(bid + ask) / 2, iv=0.20,
    )


def test_accepts_when_spread_within_threshold():
    chains = _FakeChains({"SPY": [_contract(740.0, bid=4.00, ask=4.10)]})
    guard = SpreadGuard(chain_client=chains, max_pct=0.05)
    assert guard.check(_intent()).outcome == GuardOutcome.ACCEPT


def test_rejects_when_spread_too_wide():
    chains = _FakeChains({"SPY": [_contract(740.0, bid=4.00, ask=5.00)]})
    guard = SpreadGuard(chain_client=chains, max_pct=0.05)
    res = guard.check(_intent())
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "spread_too_wide"


def test_rejects_when_leg_not_in_chain():
    chains = _FakeChains({"SPY": []})
    guard = SpreadGuard(chain_client=chains, max_pct=0.05)
    res = guard.check(_intent())
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "leg_quote_missing"


def test_rejects_when_bid_or_ask_is_zero():
    chains = _FakeChains({"SPY": [_contract(740.0, bid=0.0, ask=4.10)]})
    guard = SpreadGuard(chain_client=chains, max_pct=0.05)
    res = guard.check(_intent())
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "leg_quote_missing"
