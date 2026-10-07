"""Data-subject rights: export and erasure (PRD FR-PRIV-01/02, Compliance §6).

Export returns everything stored about the user, decrypted, as one JSON
document. Deletion removes all of it immediately (the 30-day limit in the PRD
is a ceiling, not a delay).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from koyala.escalation import Escalation
from koyala.tracking import Record, RecordKind

EXPORT_VERSION = 1


class PrivacyStore(Protocol):
    def export(self, user_id: str) -> dict[str, Any]: ...

    def delete(self, user_id: str) -> None: ...


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def record_json(rec: Record) -> dict[str, Any]:
    out: dict[str, Any] = {"id": rec.id, "created_at": _iso(rec.created_at), **rec.payload}
    if rec.kind is RecordKind.JOURNAL:
        out["private"] = rec.private
    return out


def escalation_json(esc: Escalation) -> dict[str, Any]:
    return {
        "id": esc.id,
        "channel": str(esc.channel),
        "status": str(esc.status),
        "risk_tier": esc.risk_tier,
        "language": esc.language,
        "created_at": _iso(esc.created_at),
        "connected_at": _iso(esc.connected_at),
        "closed_at": _iso(esc.closed_at),
        "callback_number": esc.callback_number,
    }


def risk_state_json(state: dict[str, Any] | None) -> dict[str, Any] | None:
    if state is None:
        return None

    def conv(v: Any) -> Any:
        if v is None or isinstance(v, datetime):
            return _iso(v)
        return int(v)

    return {k: conv(v) for k, v in state.items()}


def assemble(
    user: dict[str, Any],
    sessions: list[dict[str, Any]],
    records: list[Record],
    risk_state: dict[str, Any] | None,
    risk_events: list[dict[str, Any]],
    escalations: list[Escalation],
) -> dict[str, Any]:
    by_kind: dict[RecordKind, list[Record]] = {k: [] for k in RecordKind}
    for rec in sorted(records, key=lambda r: r.created_at):
        by_kind[rec.kind].append(rec)
    plans = by_kind[RecordKind.SAFETY_PLAN]
    return {
        "export_version": EXPORT_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "user": user,
        "chat_sessions": sessions,
        "assessments": [record_json(r) for r in by_kind[RecordKind.ASSESSMENT]],
        "mood_logs": [record_json(r) for r in by_kind[RecordKind.MOOD]],
        "journal": [record_json(r) for r in by_kind[RecordKind.JOURNAL]],
        "safety_plan": record_json(plans[-1]) if plans else None,
        "check_ins": [record_json(r) for r in by_kind[RecordKind.CHECK_IN]],
        "risk_state": risk_state_json(risk_state),
        "risk_events": risk_events,
        "escalations": [escalation_json(e) for e in escalations],
    }


class InMemoryPrivacyStore:
    """Composes the in-memory stores' export_user / delete_user methods."""

    def __init__(self, sessions, risk_states, auth, tracking, escalations) -> None:
        self._sessions = sessions
        self._risk_states = risk_states
        self._auth = auth
        self._tracking = tracking
        self._escalations = escalations

    def export(self, user_id: str) -> dict[str, Any]:
        return assemble(
            user={"id": user_id},
            sessions=self._sessions.export_user(user_id),
            records=self._tracking.export_user(user_id),
            risk_state=self._risk_states.export_user(user_id),
            risk_events=[],
            escalations=self._escalations.export_user(user_id),
        )

    def delete(self, user_id: str) -> None:
        for store in (
            self._sessions,
            self._tracking,
            self._risk_states,
            self._escalations,
            self._auth,  # last: removes the account itself
        ):
            store.delete_user(user_id)
