"""User-owned tracking records: assessments, mood logs, journal entries, safety plan.

Payloads are opaque JSON dicts here; the API layer validates their shape.
`koyala.db.stores.SqlTrackingStore` encrypts every payload with the user's key.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol


class RecordKind(StrEnum):
    ASSESSMENT = "assessment"
    MOOD = "mood"
    JOURNAL = "journal"
    SAFETY_PLAN = "safety_plan"


@dataclass(frozen=True)
class Record:
    id: str
    kind: RecordKind
    created_at: datetime
    payload: dict[str, Any]
    # Private records are excluded from all automated processing (PRD FR-JRN-02).
    private: bool = False


class TrackingStore(Protocol):
    def add(
        self,
        user_id: str,
        kind: RecordKind,
        payload: dict[str, Any],
        private: bool = False,
        now: datetime | None = None,
    ) -> Record: ...

    def list(
        self,
        user_id: str,
        kind: RecordKind,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Record]:
        """Newest first."""
        ...

    def delete(self, user_id: str, kind: RecordKind, record_id: str) -> bool: ...

    def put_single(
        self, user_id: str, kind: RecordKind, payload: dict[str, Any], now: datetime | None = None
    ) -> Record:
        """Replace the user's only record of this kind (e.g. the safety plan)."""
        ...


class InMemoryTrackingStore:
    def __init__(self) -> None:
        self._records: dict[str, list[tuple[str, Record]]] = {}
        self._lock = threading.Lock()

    def add(
        self,
        user_id: str,
        kind: RecordKind,
        payload: dict[str, Any],
        private: bool = False,
        now: datetime | None = None,
    ) -> Record:
        rec = Record(
            id=uuid.uuid4().hex,
            kind=kind,
            created_at=now or datetime.now(UTC),
            payload=dict(payload),
            private=private,
        )
        with self._lock:
            self._records.setdefault(user_id, []).append((user_id, rec))
        return rec

    def list(
        self,
        user_id: str,
        kind: RecordKind,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Record]:
        with self._lock:
            recs = [r for _, r in self._records.get(user_id, []) if r.kind == kind]
        if since is not None:
            recs = [r for r in recs if r.created_at >= since]
        recs.sort(key=lambda r: r.created_at, reverse=True)
        return [replace(r, payload=dict(r.payload)) for r in recs[:limit]]

    def delete(self, user_id: str, kind: RecordKind, record_id: str) -> bool:
        with self._lock:
            recs = self._records.get(user_id, [])
            keep = [(u, r) for u, r in recs if not (r.kind == kind and r.id == record_id)]
            self._records[user_id] = keep
            return len(keep) != len(recs)

    def put_single(
        self, user_id: str, kind: RecordKind, payload: dict[str, Any], now: datetime | None = None
    ) -> Record:
        with self._lock:
            recs = self._records.get(user_id, [])
            self._records[user_id] = [(u, r) for u, r in recs if r.kind != kind]
        return self.add(user_id, kind, payload, now=now)
