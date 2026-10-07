"""Intent detection (component C6) — keyword placeholder until a classifier is trained."""

from __future__ import annotations

import re
from enum import StrEnum


class Intent(StrEnum):
    VENT = "vent"
    SKILL = "skill"
    STOP = "stop"


_SKILL = re.compile(
    r"\b(calm (me )?down|breath(e|ing)|grounding|exercise|relax|help me (calm|relax))\b",
    re.IGNORECASE,
)
_STOP = re.compile(r"^\s*(stop|cancel|quit|exit|enough)\b", re.IGNORECASE)


def detect(text: str) -> Intent:
    if _STOP.search(text):
        return Intent.STOP
    if _SKILL.search(text):
        return Intent.SKILL
    return Intent.VENT
