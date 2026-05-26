"""LiquidityGuard tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.guards.liquidity import LiquidityGuard
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


def _contract(strike: float, volume: int, open_interest: int) -> OptionContract:
    return OptionContract(
        occ_symbol="X", underlying="SPY",
        expiry=dt.date(2026, 6, 19), strike=strike, right="C",
        bid=1.0, ask=1.1, last=1.05, iv=0.20,
        volume=volume, open_interest=open_interest,
    )


def test_accepts_when_volume_and_oi_above_thresholds():
    chains = _FakeChains({"SPY": [_contract(740.0, volume=200, open_interest=5000)]})
    guard = LiquidityGuard(chain_client=chains, min_volume=50, min_open_interest=100)
    assert guard.check(_intent()).outcome == GuardOutcome.ACCEPT


def test_rejects_when_volume_below_threshold():
    chains = _FakeChains({"SPY": [_contract(740.0, volume=10, open_interest=5000)]})
    guard = LiquidityGuard(chain_client=chains, min_volume=50, min_open_interest=100)
    res = guard.check(_intent())
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "volume_too_low"


def test_rejects_when_open_interest_below_threshold():
    chains = _FakeChains({"SPY": [_contract(740.0, volume=200, open_interest=50)]})
    guard = LiquidityGuard(chain_client=chains, min_volume=50, min_open_interest=100)
    res = guard.check(_intent())
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "open_interest_too_low"


def test_rejects_when_leg_not_in_chain():
    chains = _FakeChains({"SPY": []})
    guard = LiquidityGuard(chain_client=chains, min_volume=50, min_open_interest=100)
    res = guard.check(_intent())
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "leg_quote_missing"


def test_min_zero_means_accept_all():
    """Sanity: liquidity guard with min=0 acts as a no-op (backwards-compat safety valve)."""
    chains = _FakeChains({"SPY": [_contract(740.0, volume=0, open_interest=0)]})
    guard = LiquidityGuard(chain_client=chains, min_volume=0, min_open_interest=0)
    assert guard.check(_intent()).outcome == GuardOutcome.ACCEPT
