"""Per-turn pipeline (TDD §4).

1. Risk assessment runs on every message, before anything else.
2. Tier >= HIGH: approved crisis template; the LLM is not called.
3. Tier MODERATE: LLM asked to explore risk; resources shown inline.
4. Otherwise: continue an active exercise, offer exercises, or reflect.
5. Every LLM reply passes the output guard; failures regenerate once, then
   fall back to a safe template.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum

from koyala.dialogue import guard, intent
from koyala.dialogue.llm import ChatMessage, LLMProvider
from koyala.dialogue.prompts import PROMPT_VERSION, Action, build_system_prompt
from koyala.protocols import engine
from koyala.safety import crisis
from koyala.safety.assessor import RiskAssessor
from koyala.safety.crisis import Action as UIAction
from koyala.safety.models import RiskTier
from koyala.store import Session

log = logging.getLogger(__name__)

CONTEXT_TURNS = 6
STRICT_RETRY_SUFFIX = (
    "\n\nYour previous draft broke a hard rule. Rewrite it following every hard rule exactly."
)


class TurnType(StrEnum):
    MESSAGE = "message"
    CRISIS = "crisis"
    EXERCISE_STEP = "exercise_step"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class TurnResult:
    type: TurnType
    text: str
    risk_tier: RiskTier
    actions: tuple[UIAction, ...] = ()
    template_id: str | None = None
    exercise_id: str | None = None
    step_id: str | None = None
    prompt_version: str | None = None
    guard_violations: tuple[str, ...] = field(default=())


class Orchestrator:
    def __init__(self, assessor: RiskAssessor, llm: LLMProvider) -> None:
        self._assessor = assessor
        self._llm = llm

    def handle(self, session: Session, text: str) -> TurnResult:
        context = [m.content for m in session.history if m.role == "user"][-CONTEXT_TURNS:]
        assessment = self._assessor.assess(session.user_id, text, context)
        session.history.append(ChatMessage(role="user", content=text))

        if assessment.is_crisis:
            session.exercise_run = None
            resp = crisis.crisis_response(assessment, session.language)
            result = TurnResult(
                type=TurnType.CRISIS,
                text=resp.text,
                risk_tier=assessment.tier,
                actions=resp.actions,
                template_id=resp.template_id,
            )
        elif assessment.tier == RiskTier.MODERATE:
            session.exercise_run = None
            result = self._generate(session, Action.RISK_EXPLORE, assessment.tier)
            result = _with_actions(result, crisis.inline_resource_actions(session.language))
        elif session.exercise_run is not None:
            result = self._continue_exercise(session, text, assessment.tier)
        elif intent.detect(text) is intent.Intent.SKILL:
            result = _offer_exercises(assessment.tier, session.language)
        else:
            result = self._generate(session, Action.REFLECT, assessment.tier)

        session.history.append(ChatMessage(role="assistant", content=result.text))
        return result

    def start_exercise(self, session: Session, exercise_id: str) -> TurnResult:
        run, step = engine.start(exercise_id)
        session.exercise_run = run
        session.history.append(ChatMessage(role="assistant", content=step.render(session.language)))
        return TurnResult(
            type=TurnType.EXERCISE_STEP,
            text=step.render(session.language),
            risk_tier=RiskTier.NONE,
            exercise_id=exercise_id,
            step_id=step.id,
        )

    def _continue_exercise(self, session: Session, text: str, tier: RiskTier) -> TurnResult:
        run = session.exercise_run
        assert run is not None
        if intent.detect(text) is intent.Intent.STOP:
            session.exercise_run = None
            return TurnResult(
                type=TurnType.MESSAGE,
                text="That's completely okay — we can stop here. How are you feeling right now?",
                risk_tier=tier,
            )
        step = engine.advance(run, text)
        if step is None:
            session.exercise_run = None
            return TurnResult(
                type=TurnType.MESSAGE,
                text="We've finished the exercise. Thank you for doing it with me.",
                risk_tier=tier,
                exercise_id=run.exercise_id,
            )
        return TurnResult(
            type=TurnType.EXERCISE_STEP,
            text=step.render(session.language),
            risk_tier=tier,
            exercise_id=run.exercise_id,
            step_id=step.id,
        )

    def _generate(self, session: Session, action: Action, tier: RiskTier) -> TurnResult:
        system = build_system_prompt(action, language=session.language)
        messages = session.history[-(CONTEXT_TURNS * 2) :]
        violations: tuple[str, ...] = ()
        for attempt in range(2):
            prompt = system if attempt == 0 else system + STRICT_RETRY_SUFFIX
            try:
                draft = self._llm.generate(prompt, messages)
            except Exception:
                log.exception("LLM generation failed")
                break
            checked = guard.check(draft)
            if checked.ok:
                return TurnResult(
                    type=TurnType.MESSAGE,
                    text=draft,
                    risk_tier=tier,
                    prompt_version=PROMPT_VERSION,
                    guard_violations=violations,
                )
            violations = checked.violations
            log.warning("output guard blocked draft: %s", violations)

        resp = crisis.fallback_response(session.language)
        return TurnResult(
            type=TurnType.FALLBACK,
            text=resp.text,
            risk_tier=tier,
            actions=resp.actions,
            template_id=resp.template_id,
            guard_violations=violations,
        )


def _with_actions(result: TurnResult, extra: tuple[UIAction, ...]) -> TurnResult:
    existing = {(a.kind, a.number) for a in result.actions}
    merged = result.actions + tuple(a for a in extra if (a.kind, a.number) not in existing)
    return TurnResult(**{**result.__dict__, "actions": merged})


def _offer_exercises(tier: RiskTier, lang: str) -> TurnResult:
    # Ask permission before starting an exercise (AI Model Spec rule M2).
    actions = tuple(
        UIAction(kind="exercise", label=ex.title_for(lang), ref=ex.id)
        for ex in engine.library().values()
    )
    return TurnResult(
        type=TurnType.MESSAGE,
        text="Would you like to try a short exercise together? Pick one whenever you're ready.",
        risk_tier=tier,
        actions=actions,
    )
