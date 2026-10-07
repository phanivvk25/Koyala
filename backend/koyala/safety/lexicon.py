"""Multilingual risk lexicon fast-path (component C3).

PLACEHOLDER LEXICON: these patterns are a starting point for engineering and
tests only. Before any user exposure they must be expanded and reviewed by
clinicians and native-speaker linguists (Clinical Safety Protocol §5). The
lexicon is intentionally conservative: it may over-trigger, never the reverse.
"""

from __future__ import annotations

import re
import unicodedata

from koyala.safety.models import RiskCategory, RiskSignal, RiskTier

_C = RiskCategory
_T = RiskTier

# (tier, categories, patterns). Patterns run on normalised lower-case text.
_RULES: list[tuple[RiskTier, frozenset[RiskCategory], list[str]]] = [
    # --- Imminent: attempt in progress / means + timeframe / medical emergency
    (
        _T.IMMINENT,
        frozenset({_C.SUICIDE, _C.MEDICAL_EMERGENCY}),
        [
            r"\b(i('ve| have)|just) (taken|took|swallowed) (all |a lot of |too many )?(the )?"
            r"(pills|tablets|sleeping pills|poison)",
            r"\boverdosed?\b",
            r"\b(kill|end) (myself|my life) (tonight|now|today|right now)\b",
            r"\bthis is (my )?(goodbye|final message)\b",
            r"\bstanding on the (edge|ledge|roof|bridge)\b",
        ],
    ),
    # --- High: active ideation, plan, recent self-harm, harm to others
    (
        _T.HIGH,
        frozenset({_C.SUICIDE}),
        [
            r"\b(want|going|plan(ning)?|ready) to (kill myself|end (my life|it all)|die)\b",
            r"\bkill myself\b",
            r"\bend (my life|it all)\b",
            r"\bsuicid(e|al)\b",
            r"\bhow (would|could|do) i (do it|kill myself|end it)\b",
            r"\bbetter off dead\b",
            # Hindi / Hinglish (transliterated)
            r"\bkhud ?kushi\b",
            r"\b(mujhe )?mar(na)? (jana )?chaht[ai]\b",
            r"\baatm?ahatya\b",
            # Telugu (transliterated)
            r"\bchach(i|ip)ovaal?(ani|i)\b",
            r"\bchanipovaal?(ani|i)\b",
        ],
    ),
    (
        _T.HIGH,
        frozenset({_C.SELF_INJURY}),
        [
            r"\b(cut|cutting|burn(ed|ing)?|hurt(ing)?) myself\b",
            r"\bself[- ]?harm(ed|ing)?\b",
        ],
    ),
    (
        _T.HIGH,
        frozenset({_C.HARM_TO_OTHERS}),
        [
            r"\b(want|going) to (kill|hurt|stab|shoot) (him|her|them|someone|my \w+)\b",
        ],
    ),
    (
        _T.HIGH,
        frozenset({_C.ABUSE}),
        [
            r"\b(he|she|they|my \w+) (hits|beats|beat|hit) me\b",
            r"\b(being|was|been) (abused|molested|raped)\b",
        ],
    ),
    # --- Moderate: passive ideation
    (
        _T.MODERATE,
        frozenset({_C.SUICIDE}),
        [
            r"\bwish i (was|were) (dead|never born)\b",
            r"\bwish i (could|would) (just )?(disappear|not wake up|never wake up)\b",
            r"\bdon'?t want to (be alive|live|exist|wake up)\b",
            r"\bno (reason|point) (to|in) (live|living|going on)\b",
            r"\beveryone would be better (off )?without me\b",
            r"\bjeena nahi chaht[ai]\b",
        ],
    ),
    # --- Low: hopelessness / acute distress
    (
        _T.LOW,
        frozenset({_C.DISTRESS}),
        [
            r"\bhopeless\b",
            r"\bcan'?t (take|do) (this|it) anymore\b",
            r"\bnothing (ever )?(works|matters)\b",
            r"\bpanic attack\b",
        ],
    ),
]

_COMPILED = [(tier, cats, [re.compile(p) for p in pats]) for tier, cats, pats in _RULES]


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("’", "'")
    return re.sub(r"\s+", " ", text).strip()


def scan(text: str) -> RiskSignal:
    """Return the highest-tier lexicon hit (tier NONE if nothing matched)."""
    norm = normalise(text)
    tier = RiskTier.NONE
    categories: set[RiskCategory] = set()
    for rule_tier, rule_cats, patterns in _COMPILED:
        if any(p.search(norm) for p in patterns):
            categories |= rule_cats
            tier = max(tier, rule_tier)
    return RiskSignal(source="lexicon", tier=tier, categories=frozenset(categories))
