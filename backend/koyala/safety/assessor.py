"""Risk aggregation (AI Model Spec §4.2).

tier = max(lexicon, classifier, assessment floor, sticky floor)

Detectors may only raise the tier. If a detector fails, the assessment is
floored at MODERATE so resources are shown inline (TDD §4, fail-safe).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol

from koyala.safety import lexicon
from koyala.safety.models import RiskAssessment, RiskCategory, RiskSignal, RiskTier
from koyala.safety.risk_state import RiskStateStore

log = logging.getLogger(__name__)

FAIL_SAFE_TIER = RiskTier.MODERATE


class RiskClassifier(Protocol):
    """ML risk classifier (component C4). Not yet trained; plug in when available."""

    def classify(self, text: str, context: Sequence[str]) -> RiskSignal: ...


class RiskAssessor:
    def __init__(
        self, state_store: RiskStateStore, classifier: RiskClassifier | None = None
    ) -> None:
        self._states = state_store
        self._classifier = classifier

    def assess(
        self,
        user_id: str,
        text: str,
        context: Sequence[str] = (),
        now: datetime | None = None,
    ) -> RiskAssessment:
        now = now or datetime.now(UTC)
        signals: list[RiskSignal] = []
        degraded = False

        try:
            signals.append(lexicon.scan(text))
        except Exception:
            log.exception("lexicon scan failed")
            degraded = True

        if self._classifier is not None:
            try:
                signals.append(self._classifier.classify(text, context))
            except Exception:
                log.exception("risk classifier failed")
                degraded = True

        state = self._states.get(user_id)
        floor = state.floor(now)
        if floor > RiskTier.NONE:
            signals.append(RiskSignal(source="floor", tier=floor))
        if degraded:
            signals.append(RiskSignal(source="fail_safe", tier=FAIL_SAFE_TIER))

        tier = max((s.tier for s in signals), default=RiskTier.NONE)
        categories: set[RiskCategory] = set()
        for s in signals:
            categories |= s.categories

        self._states.record_turn(user_id, tier, now, categories)
        return RiskAssessment(
            tier=tier,
            categories=frozenset(categories),
            signals=tuple(signals),
            degraded=degraded,
        )
