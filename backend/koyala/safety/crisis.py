"""Crisis templates and helpline directory.

Crisis responses at tier >= 3 come only from approved templates; the LLM is
never asked to improvise them (Clinical Safety Protocol §2.4).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

from koyala.safety.models import RiskAssessment, RiskCategory, RiskTier

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"
DEFAULT_LANG = "en"


@dataclass(frozen=True)
class Resource:
    id: str
    label: str
    number: str
    alt_numbers: tuple[str, ...]
    categories: frozenset[str]
    available: str


@dataclass(frozen=True)
class Action:
    kind: str
    label: str
    number: str | None = None
    # Target for non-call actions, e.g. an exercise id.
    ref: str | None = None


@dataclass(frozen=True)
class CrisisResponse:
    template_id: str
    text: str
    actions: tuple[Action, ...]


def _pick(localised: dict[str, str], lang: str) -> str:
    return localised.get(lang) or localised[DEFAULT_LANG]


@cache
def _load(name: str) -> dict:
    with open(CONTENT_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def resources(lang: str = DEFAULT_LANG) -> list[Resource]:
    return [
        Resource(
            id=r["id"],
            label=_pick(r["label"], lang),
            number=r["number"],
            alt_numbers=tuple(r.get("alt_numbers", [])),
            categories=frozenset(r.get("categories", [])),
            available=r.get("available", ""),
        )
        for r in _load("resources.yaml")["resources"]
    ]


def approved_numbers() -> frozenset[str]:
    """All helpline numbers Koyala may show; used by the output guard."""
    numbers: set[str] = set()
    for r in resources():
        numbers.add(r.number)
        numbers.update(r.alt_numbers)
    return frozenset(numbers)


def _template(template_id: str) -> dict:
    for t in _load("crisis_templates.yaml")["templates"]:
        if t["id"] == template_id:
            return t
    raise KeyError(template_id)


def _select_template_id(assessment: RiskAssessment) -> str:
    if assessment.tier >= RiskTier.IMMINENT:
        return "crisis_t4"
    if RiskCategory.ABUSE in assessment.categories and RiskCategory.SUICIDE not in (
        assessment.categories
    ):
        return "crisis_t3_abuse"
    return "crisis_t3"


def _actions(template: dict, lang: str) -> tuple[Action, ...]:
    by_id = {r.id: r for r in resources(lang)}
    actions: list[Action] = []
    for kind in template["actions"]:
        if kind == "call":
            for rid in template["resources"]:
                r = by_id[rid]
                actions.append(Action(kind="call", label=f"{r.label} {r.number}", number=r.number))
        elif kind == "handoff":
            actions.append(Action(kind="handoff", label="Talk to a counsellor now"))
        elif kind == "safety_plan":
            actions.append(Action(kind="safety_plan", label="Open my safety plan"))
        elif kind == "exercises":
            actions.append(Action(kind="exercises", label="Try a calming exercise"))
    return tuple(actions)


def crisis_response(assessment: RiskAssessment, lang: str = DEFAULT_LANG) -> CrisisResponse:
    template_id = _select_template_id(assessment)
    t = _template(template_id)
    return CrisisResponse(
        template_id=f"{t['id']}_v{t['version']}_{lang}",
        text=_pick(t["text"], lang),
        actions=_actions(t, lang),
    )


def fallback_response(lang: str = DEFAULT_LANG) -> CrisisResponse:
    t = _template("fallback_unavailable")
    return CrisisResponse(
        template_id=f"{t['id']}_v{t['version']}_{lang}",
        text=_pick(t["text"], lang),
        actions=_actions(t, lang),
    )


def inline_resource_actions(lang: str = DEFAULT_LANG) -> tuple[Action, ...]:
    """Resources shown alongside a normal reply at MODERATE risk."""
    by_id = {r.id: r for r in resources(lang)}
    r = by_id["tele_manas"]
    return (
        Action(kind="call", label=f"{r.label} {r.number}", number=r.number),
        Action(kind="safety_plan", label="Open my safety plan"),
    )
