"""Counsellor handoff endpoints (Clinical Safety Protocol §7)."""

from __future__ import annotations

import hmac
import os
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

from koyala.api import schemas
from koyala.api.auth_routes import CurrentUser
from koyala.escalation import (
    STICKY_LOOKBACK,
    Channel,
    Escalation,
    EscalationService,
    InvalidTransition,
    Status,
)
from koyala.safety import crisis
from koyala.safety.risk_state import RiskStateStore

router = APIRouter(prefix="/v1")

WAITING_TEXT = (
    "A trained counsellor is being connected to you now. While you wait, I'm here, "
    "and you can also call one of these helplines straight away."
)
FAILED_TEXT = (
    "I couldn't reach a counsellor through the app just now. Please call one of these "
    "helplines — they are free and available right now."
)


def _service(request: Request) -> EscalationService:
    return request.app.state.escalations


def _risk_states(request: Request) -> RiskStateStore:
    return request.app.state.risk_states


Service = Annotated[EscalationService, Depends(_service)]


class EscalationIn(BaseModel):
    channel: Channel = Channel.CHAT
    callback_number: str | None = Field(default=None, pattern=r"^\+?[0-9][0-9 -]{6,18}[0-9]$")
    language: str = Field(default="en", pattern=r"^[a-z]{2}$")

    @model_validator(mode="after")
    def _callback_needs_number(self) -> EscalationIn:
        if self.channel is Channel.CALLBACK and not self.callback_number:
            raise ValueError("callback_number is required for a callback")
        return self


class EscalationOut(BaseModel):
    id: str
    status: Status
    channel: Channel
    created_at: datetime
    connected_at: datetime | None = None
    text: str
    # Helplines are always returned, whatever the handoff status.
    actions: list[schemas.ActionOut]


def _out(esc: Escalation, lang: str = "en") -> EscalationOut:
    helplines = [
        schemas.ActionOut(**a.__dict__)
        for a in crisis.inline_resource_actions(lang)
        if a.kind == "call"
    ]
    emergency = next(r for r in crisis.resources(lang) if r.id == "emergency")
    helplines.append(
        schemas.ActionOut(
            kind="call", label=f"{emergency.label} {emergency.number}", number=emergency.number
        )
    )
    return EscalationOut(
        id=esc.id,
        status=esc.status,
        channel=esc.channel,
        created_at=esc.created_at,
        connected_at=esc.connected_at,
        text=FAILED_TEXT if esc.status is Status.FAILED else WAITING_TEXT,
        actions=helplines,
    )


@router.post("/escalations", response_model=EscalationOut, status_code=201)
def request_counsellor(
    body: EscalationIn,
    user_id: CurrentUser,
    service: Service,
    risk_states: Annotated[RiskStateStore, Depends(_risk_states)],
) -> EscalationOut:
    now = datetime.now(UTC)
    state = risk_states.get(user_id)
    tier = state.floor(now)
    if state.peak_at and now - state.peak_at < STICKY_LOOKBACK:
        tier = max(tier, state.peak_tier)
    esc = service.request(
        user_id,
        body.channel,
        risk_tier=int(tier),
        categories=(),
        language=body.language,
        callback_number=body.callback_number,
        now=now,
    )
    return _out(esc, body.language)


@router.get("/escalations/{escalation_id}", response_model=EscalationOut)
def get_escalation(escalation_id: str, user_id: CurrentUser, service: Service) -> EscalationOut:
    esc = service.get_for_user(user_id, escalation_id)
    if esc is None:
        raise HTTPException(status_code=404, detail="escalation not found")
    return _out(esc, esc.language)


@router.post("/escalations/{escalation_id}/cancel", response_model=EscalationOut)
def cancel_escalation(escalation_id: str, user_id: CurrentUser, service: Service) -> EscalationOut:
    esc = service.get_for_user(user_id, escalation_id)
    if esc is None:
        raise HTTPException(status_code=404, detail="escalation not found")
    try:
        esc = service.update_status(escalation_id, Status.CLOSED)
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    return _out(esc, esc.language)


# --- Crisis partner callback ------------------------------------------------------------


class PartnerStatusIn(BaseModel):
    status: Status


def _check_partner_token(token: str | None) -> None:
    expected = os.environ.get("KOYALA_PARTNER_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="partner callbacks not configured")
    if token is None or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="invalid partner token")


@router.post("/partner/escalations/{escalation_id}/status", status_code=204)
def partner_status(
    escalation_id: str,
    body: PartnerStatusIn,
    service: Service,
    x_partner_token: Annotated[str | None, Header()] = None,
) -> None:
    """Called by the crisis partner when a counsellor connects or the case closes."""
    _check_partner_token(x_partner_token)
    try:
        service.update_status(escalation_id, body.status)
    except KeyError:
        raise HTTPException(status_code=404, detail="escalation not found") from None
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
