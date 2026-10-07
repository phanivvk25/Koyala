"""SQL-backed implementations of SessionStore and RiskStateStore."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, delete, select, update
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
from koyala.db.models import (
    ChatSession,
    EscalationRow,
    Message,
    RefreshToken,
    RiskEvent,
    RiskStateRow,
    User,
    UserRecord,
)
from koyala.dialogue.llm import ChatMessage
from koyala.escalation import OPEN_STATUSES, Channel, Escalation, Status
from koyala.privacy import assemble
from koyala.protocols.engine import ExerciseRun
from koyala.safety.models import RiskCategory, RiskTier
from koyala.safety.risk_state import RiskState
from koyala.store import Session
from koyala.tracking import Record, RecordKind

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

    def user_exists(self, user_id: str) -> bool:
        with self._factory() as db:
            return db.get(User, user_id) is not None

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


class SqlTrackingStore:
    def __init__(self, factory: sessionmaker[DbSession], crypto: Crypto) -> None:
        self._factory = factory
        self._crypto = crypto

    def add(
        self,
        user_id: str,
        kind: RecordKind,
        payload: dict[str, Any],
        private: bool = False,
        now: datetime | None = None,
    ) -> Record:
        now = now or datetime.now(UTC)
        with self._factory.begin() as db:
            return self._insert(db, user_id, kind, payload, private, now)

    def list(
        self,
        user_id: str,
        kind: RecordKind,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Record]:
        with self._factory() as db:
            user = db.get(User, user_id)
            if user is None:
                return []
            query = select(UserRecord).where(
                UserRecord.user_id == user_id, UserRecord.kind == str(kind)
            )
            if since is not None:
                query = query.where(UserRecord.created_at >= since)
            rows = db.scalars(query.order_by(UserRecord.created_at.desc()).limit(limit)).all()
        return [
            Record(
                id=row.id,
                kind=RecordKind(row.kind),
                created_at=_utc(row.created_at),
                payload=json.loads(
                    self._crypto.decrypt(user.dek_wrapped, user_id, row.payload_enc)
                ),
                private=row.private,
            )
            for row in rows
        ]

    def delete(self, user_id: str, kind: RecordKind, record_id: str) -> bool:
        with self._factory.begin() as db:
            result = db.execute(
                delete(UserRecord).where(
                    UserRecord.id == record_id,
                    UserRecord.user_id == user_id,
                    UserRecord.kind == str(kind),
                )
            )
        return result.rowcount > 0

    def put_single(
        self, user_id: str, kind: RecordKind, payload: dict[str, Any], now: datetime | None = None
    ) -> Record:
        now = now or datetime.now(UTC)
        with self._factory.begin() as db:
            db.execute(
                delete(UserRecord).where(
                    UserRecord.user_id == user_id, UserRecord.kind == str(kind)
                )
            )
            return self._insert(db, user_id, kind, payload, False, now)

    def _insert(
        self,
        db: DbSession,
        user_id: str,
        kind: RecordKind,
        payload: dict[str, Any],
        private: bool,
        now: datetime,
    ) -> Record:
        user = _ensure_user(db, self._crypto, user_id)
        rec = Record(
            id=uuid.uuid4().hex, kind=kind, created_at=now, payload=dict(payload), private=private
        )
        db.add(
            UserRecord(
                id=rec.id,
                user_id=user_id,
                kind=str(kind),
                created_at=now,
                private=private,
                payload_enc=self._crypto.encrypt(
                    user.dek_wrapped, user_id, json.dumps(payload, ensure_ascii=False)
                ),
            )
        )
        return rec


class SqlEscalationStore:
    def __init__(self, factory: sessionmaker[DbSession], crypto: Crypto) -> None:
        self._factory = factory
        self._crypto = crypto

    def save(self, escalation: Escalation) -> None:
        e = escalation
        with self._factory.begin() as db:
            user = _ensure_user(db, self._crypto, e.user_id)
            number_enc = (
                self._crypto.encrypt(user.dek_wrapped, e.user_id, e.callback_number)
                if e.callback_number
                else None
            )
            db.merge(
                EscalationRow(
                    id=e.id,
                    user_id=e.user_id,
                    channel=str(e.channel),
                    risk_tier=e.risk_tier,
                    categories=list(e.categories),
                    language=e.language,
                    status=str(e.status),
                    created_at=e.created_at,
                    callback_number_enc=number_enc,
                    partner_ref=e.partner_ref,
                    connected_at=e.connected_at,
                    closed_at=e.closed_at,
                    sla_breached=e.sla_breached,
                )
            )

    def get(self, escalation_id: str) -> Escalation | None:
        with self._factory() as db:
            row = db.get(EscalationRow, escalation_id)
            if row is None:
                return None
            user = db.get(User, row.user_id)
            return self._to_escalation(row, user)

    def open_before(self, cutoff: datetime) -> list[Escalation]:
        with self._factory() as db:
            rows = db.scalars(
                select(EscalationRow).where(
                    EscalationRow.status.in_([str(s) for s in OPEN_STATUSES]),
                    EscalationRow.created_at < cutoff,
                    EscalationRow.sla_breached.is_(False),
                )
            ).all()
            return [self._to_escalation(r, db.get(User, r.user_id)) for r in rows]

    def open_for_user(self, user_id: str) -> Escalation | None:
        with self._factory() as db:
            row = db.scalars(
                select(EscalationRow)
                .where(
                    EscalationRow.user_id == user_id,
                    EscalationRow.status.in_([str(s) for s in OPEN_STATUSES]),
                )
                .order_by(EscalationRow.created_at.desc())
                .limit(1)
            ).one_or_none()
            return self._to_escalation(row, db.get(User, user_id)) if row else None

    def _to_escalation(self, row: EscalationRow, user: User | None) -> Escalation:
        number = None
        if row.callback_number_enc is not None and user is not None:
            number = self._crypto.decrypt(user.dek_wrapped, row.user_id, row.callback_number_enc)
        return Escalation(
            id=row.id,
            user_id=row.user_id,
            channel=Channel(row.channel),
            risk_tier=row.risk_tier,
            categories=tuple(row.categories),
            language=row.language,
            status=Status(row.status),
            created_at=_utc(row.created_at),
            callback_number=number,
            partner_ref=row.partner_ref,
            connected_at=_utc(row.connected_at),
            closed_at=_utc(row.closed_at),
            sla_breached=row.sla_breached,
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


class SqlPrivacyStore:
    """Export and erase everything stored for a user, across all tables."""

    def __init__(
        self,
        factory: sessionmaker[DbSession],
        crypto: Crypto,
        tracking: SqlTrackingStore,
        escalations: SqlEscalationStore,
    ) -> None:
        self._factory = factory
        self._crypto = crypto
        self._tracking = tracking
        self._escalations = escalations

    def export(self, user_id: str) -> dict[str, Any]:
        with self._factory() as db:
            user = db.get(User, user_id)
            if user is None:
                return assemble({"id": user_id}, [], [], None, [], [])

            def dec(blob: bytes) -> str:
                return self._crypto.decrypt(user.dek_wrapped, user_id, blob)

            sessions = []
            for cs in db.scalars(
                select(ChatSession)
                .where(ChatSession.user_id == user_id)
                .order_by(ChatSession.created_at)
            ):
                msgs = db.scalars(
                    select(Message).where(Message.session_id == cs.id).order_by(Message.seq)
                )
                sessions.append(
                    {
                        "id": cs.id,
                        "language": cs.language,
                        "created_at": _utc(cs.created_at).isoformat(),
                        "messages": [
                            {
                                "role": m.role,
                                "content": dec(m.content_enc),
                                "created_at": _utc(m.created_at).isoformat(),
                            }
                            for m in msgs
                        ],
                    }
                )
            risk_row = db.get(RiskStateRow, user_id)
            risk_events = [
                {
                    "tier": e.tier,
                    "categories": e.categories,
                    "created_at": _utc(e.created_at).isoformat(),
                }
                for e in db.scalars(
                    select(RiskEvent)
                    .where(RiskEvent.user_id == user_id)
                    .order_by(RiskEvent.created_at)
                )
            ]
            esc_rows = db.scalars(
                select(EscalationRow)
                .where(EscalationRow.user_id == user_id)
                .order_by(EscalationRow.created_at)
            ).all()
            escalations = [self._escalations._to_escalation(r, user) for r in esc_rows]
            user_info = {
                "id": user.id,
                "auth_type": user.auth_type,
                "created_at": _utc(user.created_at).isoformat(),
            }
        records = [
            r for kind in RecordKind for r in self._tracking.list(user_id, kind, limit=1_000_000)
        ]
        return assemble(
            user_info,
            sessions,
            records,
            asdict(_to_state(risk_row)) if risk_row else None,
            risk_events,
            escalations,
        )

    def delete(self, user_id: str) -> None:
        # Explicit deletes in dependency order: correct even where the database
        # does not enforce ON DELETE CASCADE (e.g. SQLite without the pragma).
        with self._factory.begin() as db:
            session_ids = select(ChatSession.id).where(ChatSession.user_id == user_id)
            db.execute(delete(Message).where(Message.session_id.in_(session_ids)))
            for model in (
                ChatSession,
                UserRecord,
                RiskEvent,
                RiskStateRow,
                EscalationRow,
                RefreshToken,
            ):
                db.execute(delete(model).where(model.user_id == user_id))
            db.execute(delete(User).where(User.id == user_id))
