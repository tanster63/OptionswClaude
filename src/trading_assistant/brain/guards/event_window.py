"""EventWindowGuard: reject if expiry crosses a macro/earnings event for the symbol."""

from __future__ import annotations

import datetime as dt

from trading_assistant.brain.validator import GuardOutcome, GuardResult
from trading_assistant.calendars.events import EventCalendar
from trading_assistant.intents.model import TradeIntent


class EventWindowGuard:
    name = "event_window"

    def __init__(self, calendar: EventCalendar, now: dt.datetime) -> None:
        self._cal = calendar
        self._now = now

    def check(self, intent: TradeIntent) -> GuardResult:
        today = self._now.date()
        for leg in intent.legs:
            days = (leg.expiry - today).days
            if days < 0:
                continue
            events = self._cal.events_in_window(today, days)
            for ev in events:
                if intent.symbol in ev.symbols and today < ev.date <= leg.expiry:
                    return GuardResult(outcome=GuardOutcome.REJECT, reason="event_window")
        return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)
