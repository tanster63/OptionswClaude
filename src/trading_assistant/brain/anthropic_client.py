"""Thin wrapper around the Anthropic SDK for the trade-idea synthesizer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import structlog

log = structlog.get_logger(__name__)


class AnthropicError(Exception):
    """Raised when the LLM call fails for any reason we care about."""


@dataclass(frozen=True)
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int


class _AnthropicSDK(Protocol):
    """Structural subset of the Anthropic SDK we depend on."""

    messages: Any  # SDK exposes `.messages.create(...)`


class AnthropicClient:
    def __init__(self, sdk: _AnthropicSDK, model: str, max_tokens: int = 2000) -> None:
        self._sdk = sdk
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, system: str, user: str) -> LLMResponse:
        system_block = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        try:
            resp = self._sdk.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_block,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # noqa: BLE001 — intentional broad wrap
            log.warning("anthropic_call_failed", error=str(exc))
            raise AnthropicError(str(exc)) from exc

        text = "".join(getattr(block, "text", "") for block in resp.content)
        u = resp.usage
        out = LLMResponse(
            text=text,
            input_tokens=getattr(u, "input_tokens", 0),
            output_tokens=getattr(u, "output_tokens", 0),
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0),
            cache_creation_tokens=getattr(u, "cache_creation_input_tokens", 0),
        )
        log.info(
            "anthropic_call_ok",
            model=self._model,
            input_tokens=out.input_tokens,
            output_tokens=out.output_tokens,
            cache_read_tokens=out.cache_read_tokens,
            cache_creation_tokens=out.cache_creation_tokens,
        )
        return out
