"""Validator: run a candidate TradeIntent through a chain of guards."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import structlog

from trading_assistant.intents.model import TradeIntent

log = structlog.get_logger(__name__)


class GuardOutcome(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"


@dataclass(frozen=True)
class GuardResult:
    outcome: GuardOutcome
    reason: str | None


class Guard(Protocol):
    name: str

    def check(self, intent: TradeIntent) -> GuardResult: ...


class Validator:
    def __init__(self, guards: list[Guard]) -> None:
        self._guards = guards

    def validate(self, intent: TradeIntent) -> GuardResult:
        for guard in self._guards:
            result = guard.check(intent)
            if result.outcome == GuardOutcome.REJECT:
                log.info("intent_rejected", intent_id=intent.id, guard=guard.name,
                         reason=result.reason)
                return result
        log.info("intent_accepted", intent_id=intent.id)
        return GuardResult(outcome=GuardOutcome.ACCEPT, reason=None)
