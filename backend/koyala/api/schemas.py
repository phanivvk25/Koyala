from __future__ import annotations

from pydantic import BaseModel, Field

from koyala.assessments.scoring import Instrument


class CreateSessionRequest(BaseModel):
    language: str = Field(default="en", pattern=r"^[a-z]{2}$")


class CreateSessionResponse(BaseModel):
    session_id: str


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class ActionOut(BaseModel):
    kind: str
    label: str
    number: str | None = None
    ref: str | None = None


class TurnOut(BaseModel):
    type: str
    text: str
    risk_tier: int
    actions: list[ActionOut] = []
    template_id: str | None = None
    exercise_id: str | None = None
    step_id: str | None = None


class StartExerciseRequest(BaseModel):
    exercise_id: str


class ExerciseOut(BaseModel):
    id: str
    title: str
    duration_min: int
    indications: list[str]


class ResourceOut(BaseModel):
    id: str
    label: str
    number: str
    alt_numbers: list[str]
    available: str


class AssessmentRequest(BaseModel):
    instrument: Instrument
    item_scores: list[int]


class AssessmentOut(BaseModel):
    id: str
    instrument: Instrument
    total: int
    band: str
    self_harm_flag: bool
    # Set when the result requires an immediate supportive risk check-in.
    follow_up: TurnOut | None = None
