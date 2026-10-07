"""LLM provider abstraction (ai-gateway, TDD §5.3).

Production providers must be contracted with zero data retention and must
receive PII-redacted context only. `StubProvider` is an offline stand-in for
development and tests; it is not a therapeutic model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


class LLMProvider(Protocol):
    def generate(self, system: str, messages: list[ChatMessage]) -> str: ...


class LLMUnavailable(Exception):
    """Raised by providers on timeout or outage; triggers the fallback template."""


class StubProvider:
    """Deterministic reflective reply for local development."""

    def generate(self, system: str, messages: list[ChatMessage]) -> str:
        if "ACTION: RISK_EXPLORE" in system:
            return (
                "Thank you for sharing that with me. It sounds like things feel really "
                "heavy right now. Sometimes when people feel this way, they have thoughts "
                "of not wanting to be alive. Have you been having thoughts like that?"
            )
        return (
            "That sounds like a lot to carry. I'm here and listening. "
            "What feels hardest about it right now?"
        )
