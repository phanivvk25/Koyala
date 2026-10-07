"""Authentication endpoints and the `CurrentUser` dependency (TDD §9)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from koyala.auth.refresh import InvalidRefreshToken
from koyala.auth.service import AuthService, TokenPair
from koyala.auth.tokens import InvalidToken

router = APIRouter(prefix="/v1/auth")
_bearer = HTTPBearer(auto_error=False)


class TokenOut(BaseModel):
    user_id: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=16, max_length=256)


def _auth(request: Request) -> AuthService:
    return request.app.state.auth


def _out(pair: TokenPair) -> TokenOut:
    return TokenOut(
        user_id=pair.user_id,
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
    )


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    auth: Annotated[AuthService, Depends(_auth)],
) -> str:
    if creds is None or creds.scheme.lower() != "bearer":
        raise _unauthorized("missing bearer token")
    try:
        return auth.tokens.verify_access(creds.credentials)
    except InvalidToken:
        raise _unauthorized("invalid or expired token") from None


CurrentUser = Annotated[str, Depends(current_user)]


@router.post("/anonymous", response_model=TokenOut, status_code=201)
def sign_up_anonymous(auth: Annotated[AuthService, Depends(_auth)]) -> TokenOut:
    """Create an anonymous account (no name, phone or email) — PRD FR-ONB-04."""
    return _out(auth.sign_up_anonymous())


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshRequest, auth: Annotated[AuthService, Depends(_auth)]) -> TokenOut:
    try:
        return _out(auth.refresh(body.refresh_token))
    except InvalidRefreshToken:
        raise _unauthorized("invalid refresh token") from None


@router.post("/logout", status_code=204)
def logout(body: RefreshRequest, auth: Annotated[AuthService, Depends(_auth)]) -> None:
    auth.logout(body.refresh_token)
