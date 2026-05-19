"""AnthropicClient tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from trading_assistant.brain.anthropic_client import (
    AnthropicClient,
    AnthropicError,
    LLMResponse,
)


@dataclass
class _FakeUsage:
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class _FakeContent:
    text: str


@dataclass
class _FakeResp:
    content: list[_FakeContent]
    usage: _FakeUsage


class _FakeSDK:
    def __init__(self, response: _FakeResp | None = None, raise_exc: Exception | None = None) -> None:
        self._response = response
        self._raise = raise_exc
        self.last_kwargs: dict | None = None

    class _Messages:
        def __init__(self, parent: "_FakeSDK") -> None:
            self._parent = parent

        def create(self, **kwargs):  # noqa: ANN003
            self._parent.last_kwargs = kwargs
            if self._parent._raise:
                raise self._parent._raise
            return self._parent._response

    @property
    def messages(self) -> "_FakeSDK._Messages":
        return _FakeSDK._Messages(self)


def test_complete_returns_text_and_usage():
    fake = _FakeSDK(_FakeResp(
        content=[_FakeContent("hello world")],
        usage=_FakeUsage(input_tokens=100, output_tokens=20),
    ))
    client = AnthropicClient(sdk=fake, model="claude-opus-4-7", max_tokens=500)
    resp = client.complete(system="static-system", user="user msg")
    assert isinstance(resp, LLMResponse)
    assert resp.text == "hello world"
    assert resp.input_tokens == 100
    assert resp.output_tokens == 20


def test_complete_enforces_max_tokens_in_call():
    fake = _FakeSDK(_FakeResp(content=[_FakeContent("ok")], usage=_FakeUsage(1, 1)))
    client = AnthropicClient(sdk=fake, model="claude-opus-4-7", max_tokens=777)
    client.complete(system="s", user="u")
    assert fake.last_kwargs["max_tokens"] == 777


def test_complete_uses_cache_control_on_system_prompt():
    fake = _FakeSDK(_FakeResp(content=[_FakeContent("ok")], usage=_FakeUsage(1, 1)))
    client = AnthropicClient(sdk=fake, model="claude-opus-4-7", max_tokens=500)
    client.complete(system="static system text", user="user")
    system_block = fake.last_kwargs["system"]
    assert isinstance(system_block, list)
    assert system_block[0]["cache_control"] == {"type": "ephemeral"}


def test_complete_wraps_sdk_exception():
    fake = _FakeSDK(raise_exc=RuntimeError("boom"))
    client = AnthropicClient(sdk=fake, model="claude-opus-4-7", max_tokens=500)
    with pytest.raises(AnthropicError):
        client.complete(system="s", user="u")
