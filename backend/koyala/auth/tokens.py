"""Short-lived access tokens (JWT, HS256) — TDD §9."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt

ACCESS_TTL = timedelta(minutes=15)
ISSUER = "koyala"
MIN_SECRET_BYTES = 32


class InvalidToken(Exception):
    pass


class TokenService:
    def __init__(self, secret: str, access_ttl: timedelta = ACCESS_TTL) -> None:
        if len(secret.encode()) < MIN_SECRET_BYTES:
            raise ValueError(f"JWT secret must be at least {MIN_SECRET_BYTES} bytes")
        self._secret = secret
        self._ttl = access_ttl

    @property
    def access_ttl(self) -> timedelta:
        return self._ttl

    def issue_access(self, user_id: str, now: datetime | None = None) -> str:
        now = now or datetime.now(UTC)
        claims = {
            "sub": user_id,
            "iss": ISSUER,
            "typ": "access",
            "iat": now,
            "exp": now + self._ttl,
            "jti": uuid.uuid4().hex,
        }
        return jwt.encode(claims, self._secret, algorithm="HS256")

    def verify_access(self, token: str) -> str:
        """Return the user id, or raise InvalidToken."""
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                issuer=ISSUER,
                options={"require": ["sub", "exp", "iat", "iss"]},
            )
        except jwt.PyJWTError as e:
            raise InvalidToken(str(e)) from None
        if claims.get("typ") != "access":
            raise InvalidToken("wrong token type")
        return claims["sub"]
