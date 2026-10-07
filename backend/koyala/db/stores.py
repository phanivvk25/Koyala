"""SQL-backed implementations of SessionStore and RiskStateStore."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import Engine, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from koyala.auth.refresh import (
    REFRESH_TTL,
    InvalidRefreshToken,
    RefreshTokenReused,
    hash_token,
    new_token,
    new_user_id,
)
from koyala.db.crypto import Crypto
from koyala.db.models import ChatSession, Message, RefreshToken, RiskEvent, RiskStateRow, User
from koyala.dialogue.llm import ChatMessage
from koyala.protocols.engine import ExerciseRun
from koyala.safety.models import RiskCategory, RiskTier
from koyala.safety.risk_state import RiskState
from koyala.store import Session

# Messages loaded into a session's working history (the orchestrator uses fewer).
HISTORY_WINDOW = 50


def make_session_factory(engine: Engine) -> sessionmaker[DbSession]:
    return sessionmaker(engine, expire_on_commit=False)


def _ensure_user(db: DbSession, crypto: Crypto, user_id: str, auth_type: str = "anonymous") -> User:
    user = db.get(User, user_id)
    if user is not None:
        return user
    user = User(id=user_id, dek_wrapped=crypto.new_wrapped_dek(user_id), auth_type=auth_type)
    try:
        with db.begin_nested():
            db.add(user)
    except IntegrityError:
        # Created concurrently by another request.
        user = db.get(User, user_id)
        assert user is not None
    return user


def _utc(dt: datetime | None) -> datetime | None:
    # SQLite returns naive datetimes; PostgreSQL returns aware ones.
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class SqlSessionStore:
    def __init__(self, factory: sessionmaker[DbSession], crypto: Crypto) -> None:
        self._factory = factory
        self._crypto = crypto

    def create(self, user_id: str, language: str = "en") -> Session:
        with self._factory.begin() as db:
            _ensure_user(db, self._crypto, user_id)
            row = ChatSession(id=str(uuid.uuid4()), user_id=user_id, language=language)
            db.add(row)
        return Session(id=row.id, user_id=user_id, language=language)

    def get(self, session_id: str) -> Session | None:
        with self._factory() as db:
            row = db.get(ChatSession, session_id)
            if row is None:
                return None
            user = db.get(User, row.user_id)
            assert user is not None
            messages = list(
                db.scalars(
                    select(Message)
                    .where(Message.session_id == session_id)
                    .order_by(Message.seq.desc())
                    .limit(HISTORY_WINDOW)
                )
            )
        messages.reverse()

        def dec(blob: bytes) -> str:
            return self._crypto.decrypt(user.dek_wrapped, row.user_id, blob)

        history = [ChatMessage(role=m.role, content=dec(m.content_enc)) for m in messages]
        exercise_run = None
        if row.exercise_state_enc is not None:
            exercise_run = ExerciseRun(**json.loads(dec(row.exercise_state_enc)))
        return Session(
            id=row.id,
            user_id=row.user_id,
            language=row.language,
            history=history,
            exercise_run=exercise_run,
            history_offset=messages[0].seq if messages else 0,
            persisted=len(history),
        )

    def save(self, session: Session) -> None:
        with self._factory.begin() as db:
            row = db.get(ChatSession, session.id)
            user = db.get(User, session.user_id)
            if row is None or user is None:
                raise KeyError(session.id)

            def enc(text: str) -> bytes:
                return self._crypto.encrypt(user.dek_wrapped, session.user_id, text)

            for i in range(session.persisted, len(session.history)):
                m = session.history[i]
                db.add(
                    Message(
                        session_id=session.id,
                        seq=session.history_offset + i,
                        role=m.role,
                        content_enc=enc(m.content),
                    )
                )
            row.exercise_state_enc = (
                enc(json.dumps(asdict(session.exercise_run))) if session.exercise_run else None
            )
        session.persisted = len(session.history)


class SqlRiskStateStore:
    def __init__(self, factory: sessionmaker[DbSession], crypto: Crypto) -> None:
        self._factory = factory
        self._crypto = crypto

    def get(self, user_id: str) -> RiskState:
        with self._factory() as db:
            row = db.get(RiskStateRow, user_id)
            return _to_state(row) if row else RiskState()

    def record_turn(
        self,
        user_id: str,
        tier: RiskTier,
        now: datetime | None = None,
        categories: Iterable[RiskCategory] = (),
    ) -> RiskState:
        now = now or datetime.now(UTC)
        with self._factory.begin() as db:
            row = self._locked_row(db, user_id)
            state = _to_state(row)
            state.apply_turn(tier, now)
            _write(row, state)
            if tier >= RiskTier.MODERATE:
                db.add(
                    RiskEvent(
                        user_id=user_id,
                        tier=int(tier),
                        categories=sorted(str(c) for c in categories),
                        created_at=now,
                    )
                )
        return state

    def set_assessment_floor(
        self, user_id: str, tier: RiskTier, now: datetime | None = None
    ) -> None:
        now = now or datetime.now(UTC)
        with self._factory.begin() as db:
            row = self._locked_row(db, user_id)
            state = _to_state(row)
            state.apply_assessment_floor(tier, now)
            _write(row, state)

    def _locked_row(self, db: DbSession, user_id: str) -> RiskStateRow:
        """Fetch the user's row with a row lock, creating it if needed."""
        query = select(RiskStateRow).where(RiskStateRow.user_id == user_id).with_for_update()
        row = db.scalars(query).one_or_none()
        if row is not None:
            return row
        _ensure_user(db, self._crypto, user_id)
        try:
            with db.begin_nested():
                db.add(RiskStateRow(user_id=user_id, peak_tier=0, assessment_floor=0))
        except IntegrityError:
            pass  # Created concurrently; the locked select below picks it up.
        return db.scalars(query).one()


class SqlAuthStore:
    def __init__(self, factory: sessionmaker[DbSession], crypto: Crypto) -> None:
        self._factory = factory
        self._crypto = crypto

    def create_anonymous_user(self) -> str:
        user_id = new_user_id()
        with self._factory.begin() as db:
            _ensure_user(db, self._crypto, user_id, auth_type="anonymous")
        return user_id

    def issue_refresh(
        self, user_id: str, family_id: str | None = None, now: datetime | None = None
    ) -> str:
        now = now or datetime.now(UTC)
        with self._factory.begin() as db:
            return self._issue(db, user_id, family_id or uuid.uuid4().hex, now)

    def rotate(self, raw: str, now: datetime | None = None) -> tuple[str, str]:
        now = now or datetime.now(UTC)
        reused = False
        with self._factory.begin() as db:
            row = db.scalars(
                select(RefreshToken)
                .where(RefreshToken.token_hash == hash_token(raw))
                .with_for_update()
            ).one_or_none()
            if row is None or row.revoked_at is not None:
                raise InvalidRefreshToken("unknown or revoked token")
            if row.used_at is not None:
                self._revoke_family(db, row.family_id, now)
                reused = True
            elif now >= _utc(row.expires_at):
                raise InvalidRefreshToken("expired token")
            else:
                row.used_at = now
                return row.user_id, self._issue(db, row.user_id, row.family_id, now)
        # Raised after the transaction commits so the family revocation sticks.
        assert reused
        raise RefreshTokenReused("refresh token reused; family revoked")

    def revoke(self, raw: str) -> None:
        with self._factory.begin() as db:
            row = db.get(RefreshToken, hash_token(raw))
            if row is not None:
                self._revoke_family(db, row.family_id, datetime.now(UTC))

    @staticmethod
    def _issue(db: DbSession, user_id: str, family_id: str, now: datetime) -> str:
        raw = new_token()
        db.add(
            RefreshToken(
                token_hash=hash_token(raw),
                user_id=user_id,
                family_id=family_id,
                created_at=now,
                expires_at=now + REFRESH_TTL,
            )
        )
        return raw

    @staticmethod
    def _revoke_family(db: DbSession, family_id: str, now: datetime) -> None:
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )


def _to_state(row: RiskStateRow) -> RiskState:
    return RiskState(
        peak_tier=RiskTier(row.peak_tier or 0),
        peak_at=_utc(row.peak_at),
        assessment_floor=RiskTier(row.assessment_floor or 0),
        assessment_floor_at=_utc(row.assessment_floor_at),
        follow_up_due=_utc(row.follow_up_due),
    )


def _write(row: RiskStateRow, state: RiskState) -> None:
    row.peak_tier = int(state.peak_tier)
    row.peak_at = state.peak_at
    row.assessment_floor = int(state.assessment_floor)
    row.assessment_floor_at = state.assessment_floor_at
    row.follow_up_due = state.follow_up_due
