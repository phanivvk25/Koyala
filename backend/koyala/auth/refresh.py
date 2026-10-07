"""Refresh tokens: opaque, single-use, rotated on every refresh.

Only a SHA-256 hash of each token is stored. Tokens issued from one sign-in
share a family; presenting an already-used token is treated as theft and
revokes the whole family (TDD §9).
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

REFRESH_TTL = timedelta(days=30)


class InvalidRefreshToken(Exception):
    pass


class RefreshTokenReused(InvalidRefreshToken):
    pass


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_user_id() -> str:
    return f"anon_{uuid.uuid4().hex}"


class AuthStore(Protocol):
    def create_anonymous_user(self) -> str: ...

    def issue_refresh(
        self, user_id: str, family_id: str | None = None, now: datetime | None = None
    ) -> str: ...

    def rotate(self, raw: str, now: datetime | None = None) -> tuple[str, str]:
        """Consume a refresh token; return (user_id, new raw token)."""
        ...

    def revoke(self, raw: str) -> None:
        """Revoke the token's whole family (logout). Unknown tokens are ignored."""
        ...

    def user_exists(self, user_id: str) -> bool: ...


@dataclass
class _Record:
    user_id: str
    family_id: str
    expires_at: datetime
    used: bool = False
    revoked: bool = False


class InMemoryAuthStore:
    def __init__(self) -> None:
        self._tokens: dict[str, _Record] = {}
        self._users: set[str] = set()
        self._lock = threading.Lock()

    def create_anonymous_user(self) -> str:
        user_id = new_user_id()
        with self._lock:
            self._users.add(user_id)
        return user_id

    def issue_refresh(
        self, user_id: str, family_id: str | None = None, now: datetime | None = None
    ) -> str:
        now = now or datetime.now(UTC)
        raw = new_token()
        with self._lock:
            self._tokens[hash_token(raw)] = _Record(
                user_id=user_id,
                family_id=family_id or uuid.uuid4().hex,
                expires_at=now + REFRESH_TTL,
            )
        return raw

    def rotate(self, raw: str, now: datetime | None = None) -> tuple[str, str]:
        now = now or datetime.now(UTC)
        with self._lock:
            rec = self._tokens.get(hash_token(raw))
            if rec is None or rec.revoked:
                raise InvalidRefreshToken("unknown or revoked token")
            if rec.used:
                self._revoke_family(rec.family_id)
                raise RefreshTokenReused("refresh token reused; family revoked")
            if now >= rec.expires_at:
                raise InvalidRefreshToken("expired token")
            rec.used = True
        return rec.user_id, self.issue_refresh(rec.user_id, rec.family_id, now)

    def revoke(self, raw: str) -> None:
        with self._lock:
            rec = self._tokens.get(hash_token(raw))
            if rec is not None:
                self._revoke_family(rec.family_id)

    def _revoke_family(self, family_id: str) -> None:
        for rec in self._tokens.values():
            if rec.family_id == family_id:
                rec.revoked = True

    def user_exists(self, user_id: str) -> bool:
        with self._lock:
            return user_id in self._users

    def delete_user(self, user_id: str) -> None:
        with self._lock:
            self._users.discard(user_id)
            self._tokens = {h: r for h, r in self._tokens.items() if r.user_id != user_id}
