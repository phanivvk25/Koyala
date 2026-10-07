from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from koyala.dialogue.anthropic_provider import FALLBACK_BETA, AnthropicProvider
from koyala.dialogue.llm import ChatMessage, LLMUnavailable
from koyala.dialogue.redact import redact
from koyala.main import create_app

_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def _response(text="I'm here with you.", stop_reason="end_turn"):
    blocks = [SimpleNamespace(type="thinking", thinking="")]
    if text is not None:
        blocks.append(SimpleNamespace(type="text", text=text))
    return SimpleNamespace(
        content=blocks,
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category="general_harms")
        if stop_reason == "refusal"
        else None,
        _request_id="req_test",
    )


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.kwargs = None
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _generate(result):
    client = FakeClient(result)
    provider = AnthropicProvider(client=client, model="claude-opus-5-5", effort="medium")
    return provider.generate("SYSTEM", [ChatMessage(role="user", content="hi")]), client


def test_returns_text_and_sends_expected_request():
    text, client = _generate(_response())
    assert text == "I'm here with you."
    kw = client.kwargs
    assert kw["model"] == "claude-opus-5-5"
    assert kw["system"] == "SYSTEM"
    assert kw["messages"] == [{"role": "user", "content": "hi"}]
    assert kw["output_config"] == {"effort": "medium"}
    assert kw["fallbacks"] == "default" and kw["betas"] == [FALLBACK_BETA]


@pytest.mark.parametrize(
    "result",
    [
        _response(stop_reason="refusal"),
        _response(text=None),
        _response(text="   "),
        anthropic.APIConnectionError(request=_REQUEST),
        anthropic.APITimeoutError(request=_REQUEST),
        anthropic.RateLimitError(
            "slow down", response=httpx2.Response(429, request=_REQUEST), body=None
        ),
        anthropic.InternalServerError(
            "boom", response=httpx2.Response(500, request=_REQUEST), body=None
        ),
        anthropic.BadRequestError(
            "bad", response=httpx2.Response(400, request=_REQUEST), body=None
        ),
    ],
)
def test_failures_raise_llm_unavailable(result):
    with pytest.raises(LLMUnavailable):
        _generate(result)


def test_provider_failure_yields_fallback_through_api():
    provider = AnthropicProvider(client=FakeClient(_response(stop_reason="refusal")))
    client = TestClient(create_app(llm=provider))
    headers = {"X-User-Id": "u1"}
    sid = client.post("/v1/sessions", json={}, headers=headers).json()["session_id"]
    out = client.post(f"/v1/sessions/{sid}/messages", json={"text": "hi"}, headers=headers).json()
    assert out["type"] == "fallback"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mail me at priya.k@example.com", "mail me at [EMAIL]"),
        ("my number is +91 98765 43210", "my number is [PHONE]"),
        ("call 9876543210 tonight", "call [PHONE] tonight"),
        ("aadhaar 1234 5678 9012", "aadhaar [ID_NUMBER]"),
        ("PAN ABCDE1234F", "PAN [ID_NUMBER]"),
        ("see https://example.com/x", "see [URL]"),
        ("I slept 5 hours and called 14416", "I slept 5 hours and called 14416"),
    ],
)
def test_redact(text, expected):
    assert redact(text) == expected


def test_orchestrator_sends_only_redacted_text():
    seen = []

    class Capture:
        def generate(self, system, messages):
            seen.extend(m.content for m in messages)
            return "Thanks for sharing."

    client = TestClient(create_app(llm=Capture()))
    headers = {"X-User-Id": "u1"}
    sid = client.post("/v1/sessions", json={}, headers=headers).json()["session_id"]
    client.post(
        f"/v1/sessions/{sid}/messages",
        json={"text": "my email is a@b.com and phone 9876543210"},
        headers=headers,
    )
    assert seen == ["my email is [EMAIL] and phone [PHONE]"]


def test_unknown_provider_env_rejected(monkeypatch):
    monkeypatch.setenv("KOYALA_LLM_PROVIDER", "nope")
    with pytest.raises(ValueError):
        create_app()
