"""Mood logs, journal, assessment history and safety plan (PRD §4.4–4.6)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from koyala.api import schemas
from koyala.api.auth_routes import CurrentUser
from koyala.assessments.scoring import Instrument
from koyala.safety import crisis
from koyala.safety.assessor import RiskAssessor
from koyala.safety.models import RiskTier
from koyala.tracking import Record, RecordKind, TrackingStore

router = APIRouter(prefix="/v1")

SUPPORT_TEXT = (
    "Thank you for writing this down. Some of what you wrote sounds really painful. "
    "If you'd like to talk to someone, help is available right now."
)

ShortText = Annotated[str, Field(min_length=1, max_length=500)]


def _tracking(request: Request) -> TrackingStore:
    return request.app.state.tracking


def _assessor(request: Request) -> RiskAssessor:
    return request.app.state.assessor


Tracking = Annotated[TrackingStore, Depends(_tracking)]
Assessor = Annotated[RiskAssessor, Depends(_assessor)]


def screen(assessor: RiskAssessor, user_id: str, text: str) -> schemas.TurnOut | None:
    """Run user-written text through the risk layer; return support if needed."""
    if not text.strip():
        return None
    assessment = assessor.assess(user_id, text)
    if assessment.is_crisis:
        resp = crisis.crisis_response(assessment)
        return schemas.TurnOut(
            type="crisis",
            text=resp.text,
            risk_tier=int(assessment.tier),
            actions=[schemas.ActionOut(**a.__dict__) for a in resp.actions],
            template_id=resp.template_id,
        )
    if assessment.tier >= RiskTier.MODERATE:
        return schemas.TurnOut(
            type="message",
            text=SUPPORT_TEXT,
            risk_tier=int(assessment.tier),
            actions=[schemas.ActionOut(**a.__dict__) for a in crisis.inline_resource_actions()],
        )
    return None


# --- Mood ---------------------------------------------------------------------------


class MoodFactors(BaseModel):
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    exercise: bool | None = None
    social_contact: bool | None = None
    caffeine_cups: int | None = Field(default=None, ge=0, le=20)
    alcohol: bool | None = None
    period: bool | None = None


class MoodIn(BaseModel):
    score: int = Field(ge=1, le=5)
    emotions: list[Annotated[str, Field(min_length=1, max_length=32)]] = Field(
        default_factory=list, max_length=10
    )
    factors: MoodFactors = Field(default_factory=MoodFactors)
    note: str | None = Field(default=None, max_length=2000)


class MoodOut(MoodIn):
    id: str
    logged_at: datetime


class MoodCreated(MoodOut):
    support: schemas.TurnOut | None = None


def _mood_out(rec: Record) -> MoodOut:
    return MoodOut(id=rec.id, logged_at=rec.created_at, **rec.payload)


@router.post("/mood", response_model=MoodCreated, status_code=201)
def log_mood(
    body: MoodIn, user_id: CurrentUser, tracking: Tracking, assessor: Assessor
) -> MoodCreated:
    rec = tracking.add(user_id, RecordKind.MOOD, body.model_dump(exclude_none=True))
    support = screen(assessor, user_id, body.note or "")
    return MoodCreated(**_mood_out(rec).model_dump(), support=support)


@router.get("/mood", response_model=list[MoodOut])
def list_mood(
    user_id: CurrentUser,
    tracking: Tracking,
    days: Annotated[int, Query(ge=1, le=366)] = 30,
) -> list[MoodOut]:
    since = datetime.now(UTC) - timedelta(days=days)
    return [_mood_out(r) for r in tracking.list(user_id, RecordKind.MOOD, since, limit=1000)]


# --- Journal -------------------------------------------------------------------------


class JournalIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    prompt: str | None = Field(default=None, max_length=500)
    private: bool = False


class JournalOut(JournalIn):
    id: str
    created_at: datetime


class JournalCreated(JournalOut):
    support: schemas.TurnOut | None = None


def _journal_out(rec: Record) -> JournalOut:
    return JournalOut(id=rec.id, created_at=rec.created_at, private=rec.private, **rec.payload)


@router.post("/journal", response_model=JournalCreated, status_code=201)
def write_journal(
    body: JournalIn, user_id: CurrentUser, tracking: Tracking, assessor: Assessor
) -> JournalCreated:
    payload = body.model_dump(exclude={"private"}, exclude_none=True)
    rec = tracking.add(user_id, RecordKind.JOURNAL, payload, private=body.private)
    # Private entries are excluded from all automated processing (PRD FR-JRN-02).
    support = None if body.private else screen(assessor, user_id, body.text)
    return JournalCreated(**_journal_out(rec).model_dump(), support=support)


@router.get("/journal", response_model=list[JournalOut])
def list_journal(
    user_id: CurrentUser,
    tracking: Tracking,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[JournalOut]:
    return [_journal_out(r) for r in tracking.list(user_id, RecordKind.JOURNAL, limit=limit)]


@router.delete("/journal/{entry_id}", status_code=204)
def delete_journal(entry_id: str, user_id: CurrentUser, tracking: Tracking) -> None:
    if not tracking.delete(user_id, RecordKind.JOURNAL, entry_id):
        raise HTTPException(status_code=404, detail="entry not found")


# --- Assessment history ----------------------------------------------------------------


class AssessmentHistoryOut(BaseModel):
    id: str
    instrument: Instrument
    total: int
    band: str
    self_harm_flag: bool
    taken_at: datetime


@router.get("/assessments", response_model=list[AssessmentHistoryOut])
def list_assessments(
    user_id: CurrentUser,
    tracking: Tracking,
    instrument: Instrument | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AssessmentHistoryOut]:
    records = tracking.list(user_id, RecordKind.ASSESSMENT, limit=1000)
    out = [
        AssessmentHistoryOut(
            id=r.id,
            instrument=r.payload["instrument"],
            total=r.payload["total"],
            band=r.payload["band"],
            self_harm_flag=r.payload["self_harm_flag"],
            taken_at=r.created_at,
        )
        for r in records
        if instrument is None or r.payload["instrument"] == instrument
    ]
    return out[:limit]


# --- Safety plan (Stanley–Brown) ------------------------------------------------------------


class SafetyPlan(BaseModel):
    warning_signs: list[ShortText] = Field(default_factory=list, max_length=20)
    coping_strategies: list[ShortText] = Field(default_factory=list, max_length=20)
    distractions: list[ShortText] = Field(default_factory=list, max_length=20)
    support_contacts: list[ShortText] = Field(default_factory=list, max_length=20)
    professionals: list[ShortText] = Field(default_factory=list, max_length=20)
    environment_safety: list[ShortText] = Field(default_factory=list, max_length=20)
    reasons_for_living: list[ShortText] = Field(default_factory=list, max_length=20)


class SafetyPlanOut(SafetyPlan):
    updated_at: datetime | None = None


@router.get("/safety/plan", response_model=SafetyPlanOut)
def get_safety_plan(user_id: CurrentUser, tracking: Tracking) -> SafetyPlanOut:
    records = tracking.list(user_id, RecordKind.SAFETY_PLAN, limit=1)
    if not records:
        return SafetyPlanOut()
    return SafetyPlanOut(updated_at=records[0].created_at, **records[0].payload)


@router.put("/safety/plan", response_model=SafetyPlanOut)
def put_safety_plan(body: SafetyPlan, user_id: CurrentUser, tracking: Tracking) -> SafetyPlanOut:
    rec = tracking.put_single(user_id, RecordKind.SAFETY_PLAN, body.model_dump())
    return SafetyPlanOut(updated_at=rec.created_at, **rec.payload)


def assessment_payload(result: Any, item_scores: list[int]) -> dict[str, Any]:
    return {
        "instrument": str(result.instrument),
        "item_scores": list(item_scores),
        "total": result.total,
        "band": result.band,
        "self_harm_flag": result.self_harm_flag,
    }
