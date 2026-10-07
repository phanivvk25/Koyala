"""Output guard (component C13, AI Model Spec §6) — rule-based checks.

A classifier-based safety check and tone check will be added alongside these.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from koyala.safety.crisis import approved_numbers

_DIAGNOSIS = re.compile(
    r"\byou (have|are suffering from|'ve got|might have|probably have) "
    r"(clinical |major |severe )?(depression|bipolar|anxiety disorder|ocd|ptsd|adhd|"
    r"schizophrenia|borderline|personality disorder|psychosis|an eating disorder)\b",
    re.IGNORECASE,
)
_DOSAGE = re.compile(r"\b\d+(\.\d+)?\s?(mg|milligrams?|mcg|ml)\b", re.IGNORECASE)
_HUMAN_CLAIM = re.compile(
    r"\bI(?:'m| am) (a )?(real )?(human|person|therapist|psychologist|doctor|counsellor)\b",
    re.IGNORECASE,
)
_URL = re.compile(r"https?://|www\.", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s-]{1,14}\d)(?!\d)")


MIN_PHONE_DIGITS = 5


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    violations: tuple[str, ...] = ()


def check(response: str) -> GuardResult:
    violations: list[str] = []
    if _DIAGNOSIS.search(response):
        violations.append("diagnosis")
    if _DOSAGE.search(response):
        violations.append("medication_dosage")
    if _HUMAN_CLAIM.search(response):
        violations.append("human_claim")
    if _URL.search(response):
        violations.append("unapproved_url")
    allowed = {_digits(n) for n in approved_numbers()}
    for match in _PHONE.finditer(response):
        digits = _digits(match.group())
        # Short digit runs ("4-7-8 breathing", "5 things") are not phone numbers.
        if len(digits) >= MIN_PHONE_DIGITS and digits not in allowed:
            violations.append("unapproved_phone_number")
            break
    return GuardResult(ok=not violations, violations=tuple(violations))
