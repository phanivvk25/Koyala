"""Public API v1 (TDD §7.1). User endpoints require a bearer access token."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from koyala.api import schemas
from koyala.api.auth_routes import CurrentUser
from koyala.assessments import scoring
from koyala.dialogue.orchestrator import Orchestrator, TurnResult
from koyala.protocols import engine
from koyala.safety import crisis
from koyala.safety.models import RiskTier
from koyala.safety.risk_state import RiskStateStore
from koyala.store import Session, SessionStore

router = APIRouter(prefix="/v1")

ASSESSMENT_FOLLOW_UP_TEXT = (
    "Thank you for answering honestly. You mentioned having thoughts that you'd be better "
    "off dead or of hurting yourself. I'd like to check in about that — would you be "
    "willing to tell me a bit more about those thoughts?"
)


def _orchestrator(request: Request) -> Orchestrator:
    return request.app.state.orchestrator


def _sessions(request: Request) -> SessionStore:
    return request.app.state.sessions


def _risk_states(request: Request) -> RiskStateStore:
    return request.app.state.risk_states


def _owned_session(session_id: str, user_id: str, sessions: SessionStore) -> Session:
    session = sessions.get(session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="session not found")
    return session


def _turn_out(result: TurnResult) -> schemas.TurnOut:
    return schemas.TurnOut(
        type=result.type,
        text=result.text,
        risk_tier=int(result.risk_tier),
        actions=[schemas.ActionOut(**a.__dict__) for a in result.actions],
        template_id=result.template_id,
        exercise_id=result.exercise_id,
        step_id=result.step_id,
    )


@router.post("/sessions", response_model=schemas.CreateSessionResponse)
def create_session(
    body: schemas.CreateSessionRequest,
    user_id: CurrentUser,
    sessions: Annotated[SessionStore, Depends(_sessions)],
) -> schemas.CreateSessionResponse:
    return schemas.CreateSessionResponse(session_id=sessions.create(user_id, body.language).id)


@router.post("/sessions/{session_id}/messages", response_model=schemas.TurnOut)
def send_message(
    session_id: str,
    body: schemas.ChatRequest,
    user_id: CurrentUser,
    sessions: Annotated[SessionStore, Depends(_sessions)],
    orchestrator: Annotated[Orchestrator, Depends(_orchestrator)],
) -> schemas.TurnOut:
    session = _owned_session(session_id, user_id, sessions)
    result = orchestrator.handle(session, body.text)
    sessions.save(session)
    return _turn_out(result)


@router.post("/sessions/{session_id}/exercise", response_model=schemas.TurnOut)
def start_exercise(
    session_id: str,
    body: schemas.StartExerciseRequest,
    user_id: CurrentUser,
    sessions: Annotated[SessionStore, Depends(_sessions)],
    orchestrator: Annotated[Orchestrator, Depends(_orchestrator)],
) -> schemas.TurnOut:
    session = _owned_session(session_id, user_id, sessions)
    try:
        result = orchestrator.start_exercise(session, body.exercise_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="exercise not found") from None
    sessions.save(session)
    return _turn_out(result)


@router.get("/exercises", response_model=list[schemas.ExerciseOut])
def list_exercises(lang: str = "en") -> list[schemas.ExerciseOut]:
    return [
        schemas.ExerciseOut(
            id=ex.id,
            title=ex.title_for(lang),
            duration_min=ex.duration_min,
            indications=list(ex.indications),
        )
        for ex in engine.library().values()
    ]


@router.get("/safety/resources", response_model=list[schemas.ResourceOut])
def safety_resources(lang: str = "en") -> list[schemas.ResourceOut]:
    return [
        schemas.ResourceOut(
            id=r.id,
            label=r.label,
            number=r.number,
            alt_numbers=list(r.alt_numbers),
            available=r.available,
        )
        for r in crisis.resources(lang)
    ]


@router.post("/assessments", response_model=schemas.AssessmentOut)
def submit_assessment(
    body: schemas.AssessmentRequest,
    user_id: CurrentUser,
    risk_states: Annotated[RiskStateStore, Depends(_risk_states)],
) -> schemas.AssessmentOut:
    try:
        result = scoring.score(body.instrument, body.item_scores)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None

    follow_up = None
    if result.self_harm_flag:
        # PHQ-9 item 9 > 0: floor risk at MODERATE and check in (PRD FR-ONB-09).
        risk_states.set_assessment_floor(user_id, RiskTier.MODERATE)
        follow_up = schemas.TurnOut(
            type="message",
            text=ASSESSMENT_FOLLOW_UP_TEXT,
            risk_tier=int(RiskTier.MODERATE),
            actions=[schemas.ActionOut(**a.__dict__) for a in crisis.inline_resource_actions()],
        )
    return schemas.AssessmentOut(
        instrument=result.instrument,
        total=result.total,
        band=result.band,
        self_harm_flag=result.self_harm_flag,
        follow_up=follow_up,
    )
