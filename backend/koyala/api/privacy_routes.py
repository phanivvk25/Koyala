"""Data export and account deletion (PRD FR-PRIV-01/02)."""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from koyala.api.auth_routes import CurrentUser
from koyala.privacy import PrivacyStore

router = APIRouter(prefix="/v1/privacy")


def _privacy(request: Request) -> PrivacyStore:
    return request.app.state.privacy


Privacy = Annotated[PrivacyStore, Depends(_privacy)]


@router.get("/export")
def export_data(user_id: CurrentUser, privacy: Privacy) -> Response:
    """Everything Koyala stores about the user, decrypted, as a JSON download."""
    data: dict[str, Any] = privacy.export(user_id)
    return Response(
        content=json.dumps(data, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="koyala-export.json"',
            "Cache-Control": "no-store",
        },
    )


class DeleteAccountRequest(BaseModel):
    # Explicit confirmation so a stray request can't erase an account.
    confirm: Literal["DELETE"]


@router.post("/delete-account", status_code=204)
def delete_account(body: DeleteAccountRequest, user_id: CurrentUser, privacy: Privacy) -> None:
    """Permanently erase the account and all its data, immediately."""
    privacy.delete(user_id)
