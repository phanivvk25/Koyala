"""PII redaction before text leaves Koyala for an external model (TDD §5.3, component C2).

Regex-based first pass: emails, URLs, phone numbers, Aadhaar-like and PAN-like
IDs. Person and place names need an NER model and are not yet redacted.
"""

from __future__ import annotations

import re

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("[EMAIL]", re.compile(r"\b[\w.+-]+@[\w-]+(\.[\w-]+)+\b")),
    ("[URL]", re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)),
    # Aadhaar: 12 digits, optionally grouped 4-4-4.
    ("[ID_NUMBER]", re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")),
    # PAN: 5 letters, 4 digits, 1 letter.
    ("[ID_NUMBER]", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    # Phone numbers: optional country code, then 10 digits with optional separators.
    ("[PHONE]", re.compile(r"(?<!\d)(?:\+\d{1,3}[\s-]?)?(?:\d[\s-]?){9}\d(?!\d)")),
]


def redact(text: str) -> str:
    for placeholder, pattern in _PATTERNS:
        text = pattern.sub(placeholder, text)
    return text
