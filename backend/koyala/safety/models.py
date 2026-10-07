"""Risk tiers and categories — see docs/05-AI-Model-Specification.md §4."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum


class RiskTier(IntEnum):
    NONE = 0
    LOW = 1
    MODERATE = 2
    HIGH = 3
    IMMINENT = 4


class RiskCategory(StrEnum):
    SUICIDE = "SUI"
    SELF_INJURY = "NSSI"
    HARM_TO_OTHERS = "HTO"
    ABUSE = "ABU"
    MEDICAL_EMERGENCY = "MED"
    PSYCHOSIS = "PSY"
    EATING_DISORDER = "EAT"
    SUBSTANCE = "SUB"
    MINOR = "MIN"
    DISTRESS = "DIS"


@dataclass(frozen=True)
class RiskSignal:
    """Output of a single detector (lexicon, classifier, judge, floors)."""

    source: str
    tier: RiskTier
    categories: frozenset[RiskCategory] = frozenset()


@dataclass(frozen=True)
class RiskAssessment:
    tier: RiskTier
    categories: frozenset[RiskCategory]
    signals: tuple[RiskSignal, ...] = field(default_factory=tuple)
    # True when a detector failed and the fail-safe floor was applied.
    degraded: bool = False

    @property
    def is_crisis(self) -> bool:
        return self.tier >= RiskTier.HIGH
