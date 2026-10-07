"""Database schema (TDD §6, MVP subset). Change only together with a migration."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Per-user data key, wrapped by the master key (koyala.db.crypto).
    dek_wrapped: Mapped[bytes] = mapped_column(LargeBinary)
    # How the account was created: "anonymous" now; "phone" / "email" / "sso" later.
    auth_type: Mapped[str] = mapped_column(String(16), server_default="anonymous")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    language: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Active exercise run as encrypted JSON (it holds the user's exercise replies).
    exercise_state_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("session_id", "seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    content_enc: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RiskStateRow(Base):
    __tablename__ = "risk_states"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    peak_tier: Mapped[int] = mapped_column(SmallInteger, default=0)
    peak_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assessment_floor: Mapped[int] = mapped_column(SmallInteger, default=0)
    assessment_floor_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    follow_up_due: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class RiskEvent(Base):
    """Audit trail of elevated-risk turns (Safety Protocol §12–13). No message content."""

    __tablename__ = "risk_events"
    __table_args__ = (Index("ix_risk_events_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tier: Mapped[int] = mapped_column(SmallInteger)
    categories: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RefreshToken(Base):
    """Refresh tokens (hashed). See koyala.auth.refresh."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_family", "family_id"),)

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserRecord(Base):
    """Assessments, mood logs, journal entries and safety plans (koyala.tracking).

    Everything the user wrote or answered is in payload_enc; only the kind,
    timestamp and private flag are stored in the clear, for querying.
    """

    __tablename__ = "user_records"
    __table_args__ = (Index("ix_user_records_user_kind_created", "user_id", "kind", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    private: Mapped[bool] = mapped_column(Boolean, default=False)
    payload_enc: Mapped[bytes] = mapped_column(LargeBinary)
