"""In-app follow-up check-ins."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from koyala.api import schemas
from koyala.api.auth_routes import CurrentUser
from koyala.followups import ACKNOWLEDGED, PENDING
from koyala.safety import crisis
from koyala.tracking import Record, RecordKind, TrackingStore

router = APIRouter(prefix="/v1/check-ins")


def _tracking(request: Request) -> TrackingStore:
    return request.app.state.tracking


Tracking = Annotated[TrackingStore, Depends(_tracking)]


class CheckInOut(BaseModel):
    id: str
    text: str
    status: str
    created_at: datetime
    actions: list[schemas.ActionOut]


def _out(rec: Record) -> CheckInOut:
    actions = crisis.follow_up_message(rec.payload.get("tier", 2)).actions
    return CheckInOut(
        id=rec.id,
        text=rec.payload["text"],
        status=rec.payload["status"],
        created_at=rec.created_at,
        actions=[schemas.ActionOut(**a.__dict__) for a in actions],
    )


@router.get("", response_model=list[CheckInOut])
def list_check_ins(
    user_id: CurrentUser, tracking: Tracking, pending: bool = True
) -> list[CheckInOut]:
    records = tracking.list(user_id, RecordKind.CHECK_IN, limit=50)
    return [_out(r) for r in records if not pending or r.payload.get("status") == PENDING]


@router.post("/{check_in_id}/ack", response_model=CheckInOut)
def acknowledge(check_in_id: str, user_id: CurrentUser, tracking: Tracking) -> CheckInOut:
    current = next(
        (r for r in tracking.list(user_id, RecordKind.CHECK_IN, limit=200) if r.id == check_in_id),
        None,
    )
    if current is None:
        raise HTTPException(status_code=404, detail="check-in not found")
    rec = tracking.update(
        user_id, RecordKind.CHECK_IN, check_in_id, {**current.payload, "status": ACKNOWLEDGED}
    )
    assert rec is not None
    return _out(rec)
