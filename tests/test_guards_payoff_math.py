"""PayoffMathGuard tests."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.guards.payoff_math import PayoffMathGuard
from trading_assistant.brain.validator import GuardOutcome
from trading_assistant.ingest.options_chain import OptionContract
from trading_assistant.intents.model import Leg, Strategy, TradeIntent


_EXP = dt.date(2026, 6, 18)
_NOW = dt.datetime(2026, 5, 27, tzinfo=dt.timezone.utc)


class _FakeChains:
    def __init__(self, chains: dict[str, list[OptionContract]]) -> None:
        self._c = chains

    def chain(self, symbol: str) -> list[OptionContract]:
        return self._c.get(symbol, [])


def _c(strike: float, right: str, bid: float, ask: float) -> OptionContract:
    return OptionContract(
        occ_symbol="X", underlying="SPY", expiry=_EXP, strike=strike, right=right,
        bid=bid, ask=ask, last=(bid + ask) / 2, iv=0.20,
    )


def test_long_call_correct_max_loss_passes():
    chains = _FakeChains({"SPY": [_c(750.0, "C", bid=10.50, ask=10.55)]})
    intent = TradeIntent(
        id="i", created_at=_NOW, signal_ids=["s"], symbol="SPY",
        strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=750.0, expiry=_EXP, qty=1)],
        rationale_md="x", max_loss_usd=1055.0, max_gain_usd=None, confidence=0.5,
    )
    guard = PayoffMathGuard(chain_client=chains)
    assert guard.check(intent).outcome == GuardOutcome.ACCEPT


def test_long_call_wrong_max_loss_rejects():
    chains = _FakeChains({"SPY": [_c(750.0, "C", bid=10.50, ask=10.55)]})
    intent = TradeIntent(
        id="i", created_at=_NOW, signal_ids=["s"], symbol="SPY",
        strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=750.0, expiry=_EXP, qty=1)],
        rationale_md="x", max_loss_usd=500.0, max_gain_usd=None, confidence=0.5,
    )
    res = PayoffMathGuard(chain_client=chains).check(intent)
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "pnl_math_incorrect_max_loss"


def test_bull_call_spread_correct_math_passes():
    """750/752 bull call spread, ask 10.55, bid 9.43.
    net_debit = (10.55 - 9.43) * 100 = $112.
    max_gain = (752-750)*100 - 112 = $88."""
    chains = _FakeChains({"SPY": [
        _c(750.0, "C", bid=10.50, ask=10.55),
        _c(752.0, "C", bid=9.43, ask=9.48),
    ]})
    intent = TradeIntent(
        id="i", created_at=_NOW, signal_ids=["s"], symbol="SPY",
        strategy=Strategy.BULL_CALL_SPREAD,
        legs=[
            Leg(side="buy", right="C", strike=750.0, expiry=_EXP, qty=1),
            Leg(side="sell", right="C", strike=752.0, expiry=_EXP, qty=1),
        ],
        rationale_md="x", max_loss_usd=112.0, max_gain_usd=88.0, confidence=0.5,
    )
    assert PayoffMathGuard(chain_client=chains).check(intent).outcome == GuardOutcome.ACCEPT


def test_bull_call_spread_hallucinated_max_gain_rejects():
    """Replicates today's bug: Claude says max_gain=$188 but actual is $88."""
    chains = _FakeChains({"SPY": [
        _c(750.0, "C", bid=10.50, ask=10.55),
        _c(752.0, "C", bid=9.43, ask=9.48),
    ]})
    intent = TradeIntent(
        id="i", created_at=_NOW, signal_ids=["s"], symbol="SPY",
        strategy=Strategy.BULL_CALL_SPREAD,
        legs=[
            Leg(side="buy", right="C", strike=750.0, expiry=_EXP, qty=1),
            Leg(side="sell", right="C", strike=752.0, expiry=_EXP, qty=1),
        ],
        rationale_md="x", max_loss_usd=112.0, max_gain_usd=188.0, confidence=0.5,
    )
    res = PayoffMathGuard(chain_client=chains).check(intent)
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "pnl_math_incorrect_max_gain"


def test_bear_put_spread_correct_math_passes():
    """750/745 bear put spread (long higher strike, short lower strike).
    net_debit = (long_ask - short_bid) = 8.20 - 5.10 = $3.10 * 100 = $310.
    max_gain = (750-745)*100 - 310 = $190."""
    chains = _FakeChains({"SPY": [
        _c(750.0, "P", bid=8.10, ask=8.20),
        _c(745.0, "P", bid=5.10, ask=5.20),
    ]})
    intent = TradeIntent(
        id="i", created_at=_NOW, signal_ids=["s"], symbol="SPY",
        strategy=Strategy.BEAR_PUT_SPREAD,
        legs=[
            Leg(side="buy", right="P", strike=750.0, expiry=_EXP, qty=1),
            Leg(side="sell", right="P", strike=745.0, expiry=_EXP, qty=1),
        ],
        rationale_md="x", max_loss_usd=310.0, max_gain_usd=190.0, confidence=0.5,
    )
    assert PayoffMathGuard(chain_client=chains).check(intent).outcome == GuardOutcome.ACCEPT


def test_long_put_correct_math_passes():
    """LONG_PUT: max_loss = premium, max_gain = strike*100 - premium."""
    chains = _FakeChains({"SPY": [_c(700.0, "P", bid=5.00, ask=5.10)]})
    intent = TradeIntent(
        id="i", created_at=_NOW, signal_ids=["s"], symbol="SPY",
        strategy=Strategy.LONG_PUT,
        legs=[Leg(side="buy", right="P", strike=700.0, expiry=_EXP, qty=1)],
        rationale_md="x", max_loss_usd=510.0,
        max_gain_usd=(700.0 * 100 - 510.0),  # 69490.0
        confidence=0.5,
    )
    assert PayoffMathGuard(chain_client=chains).check(intent).outcome == GuardOutcome.ACCEPT


def test_rejects_when_leg_not_in_chain():
    chains = _FakeChains({"SPY": []})
    intent = TradeIntent(
        id="i", created_at=_NOW, signal_ids=["s"], symbol="SPY",
        strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=750.0, expiry=_EXP, qty=1)],
        rationale_md="x", max_loss_usd=100.0, max_gain_usd=None, confidence=0.5,
    )
    res = PayoffMathGuard(chain_client=chains).check(intent)
    assert res.outcome == GuardOutcome.REJECT
    assert res.reason == "leg_quote_missing"


def test_tolerance_allows_small_rounding():
    """5% tolerance or $20 minimum should accept small drift."""
    chains = _FakeChains({"SPY": [_c(750.0, "C", bid=10.50, ask=10.55)]})
    # Computed = 10.55 * 100 = 1055; stated = 1075 (within $20)
    intent = TradeIntent(
        id="i", created_at=_NOW, signal_ids=["s"], symbol="SPY",
        strategy=Strategy.LONG_CALL,
        legs=[Leg(side="buy", right="C", strike=750.0, expiry=_EXP, qty=1)],
        rationale_md="x", max_loss_usd=1075.0, max_gain_usd=None, confidence=0.5,
    )
    assert PayoffMathGuard(chain_client=chains).check(intent).outcome == GuardOutcome.ACCEPT
