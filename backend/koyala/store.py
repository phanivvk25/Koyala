"""Chat session storage.

`InMemorySessionStore` is for tests and local development. Production uses
`koyala.db.stores.SqlSessionStore` (PostgreSQL, encrypted message content).
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from koyala.dialogue.llm import ChatMessage
from koyala.protocols.engine import ExerciseRun


@dataclass
class Session:
    id: str
    user_id: str
    language: str = "en"
    history: list[ChatMessage] = field(default_factory=list)
    exercise_run: ExerciseRun | None = None
    # Sequence number of history[0] (stores may load only the recent tail).
    history_offset: int = 0
    # Number of history entries already persisted.
    persisted: int = 0


class SessionStore(Protocol):
    def create(self, user_id: str, language: str = "en") -> Session: ...

    def get(self, session_id: str) -> Session | None: ...

    def save(self, session: Session) -> None:
        """Persist new history entries and the current exercise state."""
        ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self, user_id: str, language: str = "en") -> Session:
        session = Session(id=str(uuid.uuid4()), user_id=user_id, language=language)
        with self._lock:
            self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def save(self, session: Session) -> None:
        session.persisted = len(session.history)

    def export_user(self, user_id: str) -> list[dict]:
        with self._lock:
            sessions = [s for s in self._sessions.values() if s.user_id == user_id]
        return [
            {
                "id": s.id,
                "language": s.language,
                "messages": [{"role": m.role, "content": m.content} for m in s.history],
            }
            for s in sessions
        ]

    def delete_user(self, user_id: str) -> None:
        with self._lock:
            self._sessions = {k: v for k, v in self._sessions.items() if v.user_id != user_id}
