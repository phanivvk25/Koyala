"""In-memory session store for the MVP scaffold.

Replace with PostgreSQL (encrypted content columns) per TDD §6 before any
real user data is handled.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field

from koyala.dialogue.llm import ChatMessage
from koyala.protocols.engine import ExerciseRun


@dataclass
class Session:
    id: str
    user_id: str
    language: str = "en"
    history: list[ChatMessage] = field(default_factory=list)
    exercise_run: ExerciseRun | None = None


class SessionStore:
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
