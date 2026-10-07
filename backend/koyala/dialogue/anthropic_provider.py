"""Claude-backed LLM provider (ai-gateway, TDD §5.3).

Every failure — network, API error, timeout, refusal, empty reply — surfaces as
LLMUnavailable so the orchestrator serves the safe fallback template. Callers
must pass PII-redacted messages (see koyala.dialogue.redact).
"""

from __future__ import annotations

import logging
import os

import anthropic

from koyala.dialogue.llm import ChatMessage, LLMUnavailable

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "medium"
# Thinking tokens count against max_tokens, so leave room beyond the short reply.
DEFAULT_MAX_TOKENS = 4000
DEFAULT_TIMEOUT_S = 30.0
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    def __init__(
        self,
        client: anthropic.Anthropic | None = None,
        model: str | None = None,
        effort: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self._client = client or anthropic.Anthropic(timeout=timeout_s, max_retries=1)
        self._model = model or os.environ.get("KOYALA_LLM_MODEL", DEFAULT_MODEL)
        self._effort = effort or os.environ.get("KOYALA_LLM_EFFORT", DEFAULT_EFFORT)
        self._max_tokens = max_tokens

    def generate(self, system: str, messages: list[ChatMessage]) -> str:
        try:
            response = self._client.beta.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                output_config={"effort": self._effort},
                # On a safety-classifier decline, retry server-side on the
                # model Anthropic recommends for that refusal category.
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.RateLimitError as e:
            raise LLMUnavailable("rate limited") from e
        except anthropic.APIStatusError as e:
            log.error("LLM API error status=%s type=%s", e.status_code, getattr(e, "type", None))
            raise LLMUnavailable(f"api error {e.status_code}") from e
        except anthropic.APIConnectionError as e:
            # Includes APITimeoutError.
            raise LLMUnavailable("connection error") from e

        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None)
            log.warning("LLM refusal category=%s request_id=%s", category, response._request_id)
            raise LLMUnavailable("refusal")

        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if not text:
            log.warning("LLM returned no text stop_reason=%s", response.stop_reason)
            raise LLMUnavailable("empty response")
        return text
