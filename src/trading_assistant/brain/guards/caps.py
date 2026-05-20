"""Caps guards: per-day idea count cap and per-day realized-loss cap."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.validator import GuardOutcome, GuardResult
from trading_assistant.db.repositories import AppStateRepo
from trading_assistant.intents.model import TradeIntent
from trading_assistant.intents.repo import TradeIntentRepo


class IdeaCapGuard:
    name = "idea_cap"

    def __init__(self, intent_repo: TradeIntentRepo, cap: int, now: dt.datetime) -> None:
        self._repo = intent_repo
        self._cap = cap
        self._now = now

    def check(self, intent: TradeIntent) -> GuardResult:
        today_start = dt.datetime(self._now.year, self._now.month, self._now.day,
                                   tzinfo=dt.timezone.utc)
        rows = self._repo.list_since(today_start)
        validated_today = sum(1 for r in rows if r.status == "validated")
        if validated_today >= self._cap:
            return GuardResult(outcome=GuardOutcome.REJECT, reason="idea_cap_reached")
        return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)


class DailyLossCapGuard:
    name = "daily_loss_cap"

    def __init__(self, state_repo: AppStateRepo, loss_cap_usd: float) -> None:
        self._state = state_repo
        self._cap = loss_cap_usd

    def check(self, intent: TradeIntent) -> GuardResult:
        raw = self._state.get("daily_realized_pnl_usd")
        pnl = float(raw) if raw is not None else 0.0
        if pnl <= -self._cap:
            return GuardResult(outcome=GuardOutcome.REJECT, reason="daily_loss_cap_hit")
        return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)
