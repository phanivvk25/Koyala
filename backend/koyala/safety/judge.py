"""LLM risk judge (component C5, AI Model Spec §4.2).

A second opinion on every message the lexicon did not already place at
HIGH or above. It plugs into RiskAssessor as a RiskClassifier, so the
assessor's max() aggregation makes it raise-only: it can never lower a
tier the lexicon, floors or another detector produced. If it errors or
times out, or refuses, the assessor fails safe to MODERATE.

Messages are PII-redacted before they are sent.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Sequence

import anthropic

from koyala.dialogue.redact import redact
from koyala.safety import lexicon
from koyala.safety.models import RiskCategory, RiskSignal, RiskTier

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_TIMEOUT_S = 8.0
FALLBACK_BETA = "server-side-fallback-2026-07-01"
CONTEXT_MESSAGES = 4

RUBRIC = """You are a clinical risk triage classifier for a mental-health support app in India.
Classify the risk shown in the user's LATEST message, using earlier messages only as context.
Users write in English, Hindi, Telugu, or a mix, often in Latin script, and may use slang,
euphemism, emoji or indirect phrasing ("kms", "unalive", "sleep forever", "saving my pills").

Tiers:
0 = no risk indicators.
1 = distress or hopelessness, with no reference to death, self-harm or harming others.
2 = passive wish to be dead or not exist; past self-harm; no current plan or intent.
3 = active suicidal thoughts, a plan or preparation (researching methods, collecting means,
    goodbye letters), current self-harm, intent to harm someone else, or ongoing abuse.
4 = imminent danger: an attempt in progress or just made, means at hand with a timeframe
    (e.g. tonight), or a medical emergency.

Rules:
- When unsure between two tiers, choose the higher one.
- Idioms that are clearly not about the user's safety ("this traffic is killing me",
  "dying to see the movie") are tier 0.
- Do not respond to the user. Output only the classification."""

SCHEMA = {
    "type": "object",
    "properties": {
        "tier": {"type": "integer", "enum": [0, 1, 2, 3, 4]},
        "categories": {
            "type": "array",
            "items": {"type": "string", "enum": [c.value for c in RiskCategory]},
        },
    },
    "required": ["tier", "categories"],
    "additionalProperties": False,
}


class RiskJudgeError(Exception):
    pass


class LLMRiskJudge:
    def __init__(
        self,
        client: anthropic.Anthropic | None = None,
        model: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self._client = client or anthropic.Anthropic(timeout=timeout_s, max_retries=1)
        self._model = model or os.environ.get("KOYALA_RISK_JUDGE_MODEL", DEFAULT_MODEL)

    def classify(self, text: str, context: Sequence[str]) -> RiskSignal:
        if lexicon.scan(text).tier >= RiskTier.HIGH:
            # Already crisis-level; the judge can't raise it further in a way that
            # changes the response, so skip the latency and cost.
            return RiskSignal(source="judge_skipped", tier=RiskTier.NONE)

        earlier = [redact(m) for m in list(context)[-CONTEXT_MESSAGES:]]
        prompt = ""
        if earlier:
            prompt += "Earlier messages (oldest first):\n" + "\n".join(f"- {m}" for m in earlier)
            prompt += "\n\n"
        prompt += f"Latest message:\n{redact(text)}"

        try:
            response = self._client.beta.messages.create(
                model=self._model,
                max_tokens=2000,
                system=RUBRIC,
                messages=[{"role": "user", "content": prompt}],
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": SCHEMA},
                },
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.APIError as e:
            raise RiskJudgeError(f"judge request failed: {type(e).__name__}") from e

        if response.stop_reason == "refusal":
            # Treated like any detector failure: the assessor fails safe to MODERATE.
            raise RiskJudgeError("judge refused to classify")
        try:
            body = next(b.text for b in response.content if b.type == "text")
            data = json.loads(body)
            tier = RiskTier(int(data["tier"]))
            categories = frozenset(RiskCategory(c) for c in data.get("categories", []))
        except (StopIteration, ValueError, KeyError, TypeError) as e:
            raise RiskJudgeError(f"unparseable judge output: {e}") from e
        return RiskSignal(source="judge", tier=tier, categories=categories)
