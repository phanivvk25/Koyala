from __future__ import annotations

import logging
from dataclasses import dataclass

from koyala.auth.refresh import AuthStore, RefreshTokenReused
from koyala.auth.tokens import TokenService

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenPair:
    user_id: str
    access_token: str
    refresh_token: str
    expires_in: int


class AuthService:
    def __init__(self, tokens: TokenService, store: AuthStore) -> None:
        self.tokens = tokens
        self._store = store

    def sign_up_anonymous(self) -> TokenPair:
        user_id = self._store.create_anonymous_user()
        return self._pair(user_id, self._store.issue_refresh(user_id))

    def refresh(self, refresh_token: str) -> TokenPair:
        try:
            user_id, new_refresh = self._store.rotate(refresh_token)
        except RefreshTokenReused:
            log.warning("refresh token reuse detected; token family revoked")
            raise
        return self._pair(user_id, new_refresh)

    def logout(self, refresh_token: str) -> None:
        self._store.revoke(refresh_token)

    def _pair(self, user_id: str, refresh_token: str) -> TokenPair:
        return TokenPair(
            user_id=user_id,
            access_token=self.tokens.issue_access(user_id),
            refresh_token=refresh_token,
            expires_in=int(self.tokens.access_ttl.total_seconds()),
        )
