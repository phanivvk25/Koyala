"""Exercise protocol engine (component C10, TDD §7.3).

Exercises are deterministic state machines defined in YAML. The engine decides
which step comes next; an LLM may only rephrase steps marked paraphrase-allowed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import yaml

EXERCISE_DIR = Path(__file__).resolve().parent.parent / "content" / "exercises"
DEFAULT_LANG = "en"


@dataclass(frozen=True)
class Step:
    id: str
    text: dict[str, str]
    expects_reply: bool = False
    llm_paraphrase: bool = False

    def render(self, lang: str) -> str:
        return self.text.get(lang) or self.text[DEFAULT_LANG]


@dataclass(frozen=True)
class Exercise:
    id: str
    version: int
    title: dict[str, str]
    duration_min: int
    indications: tuple[str, ...]
    steps: tuple[Step, ...]
    approved: bool

    def title_for(self, lang: str) -> str:
        return self.title.get(lang) or self.title[DEFAULT_LANG]


@dataclass
class ExerciseRun:
    exercise_id: str
    step_index: int = 0
    pre_distress: int | None = None
    post_distress: int | None = None
    replies: dict[str, str] = field(default_factory=dict)

    @property
    def finished(self) -> bool:
        return self.step_index >= len(get_exercise(self.exercise_id).steps)


def _parse(raw: dict) -> Exercise:
    steps = tuple(
        Step(
            id=s["id"],
            text=s["text"],
            expects_reply=s.get("expects_reply", False),
            llm_paraphrase=s.get("llm_paraphrase", False),
        )
        for s in raw["steps"]
    )
    if not steps:
        raise ValueError(f"exercise {raw['id']} has no steps")
    return Exercise(
        id=raw["id"],
        version=raw["version"],
        title=raw["title"],
        duration_min=raw["duration_min"],
        indications=tuple(raw.get("indications", [])),
        steps=steps,
        approved=raw.get("approved", False),
    )


@cache
def library() -> dict[str, Exercise]:
    exercises = {}
    for path in sorted(EXERCISE_DIR.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            ex = _parse(yaml.safe_load(f))
        exercises[ex.id] = ex
    return exercises


def get_exercise(exercise_id: str) -> Exercise:
    try:
        return library()[exercise_id]
    except KeyError:
        raise KeyError(f"unknown exercise: {exercise_id}") from None


def start(exercise_id: str) -> tuple[ExerciseRun, Step]:
    ex = get_exercise(exercise_id)
    return ExerciseRun(exercise_id=ex.id), ex.steps[0]


def advance(run: ExerciseRun, user_reply: str | None = None) -> Step | None:
    """Record the reply to the current step and return the next step (None when done)."""
    ex = get_exercise(run.exercise_id)
    if run.finished:
        return None
    current = ex.steps[run.step_index]
    if user_reply is not None and current.expects_reply:
        run.replies[current.id] = user_reply
    run.step_index += 1
    return None if run.finished else ex.steps[run.step_index]
