"""Per-user risk state: sticky floors and follow-up scheduling (Safety Protocol §9)."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from koyala.safety.models import RiskTier

# After a turn at tier X, later turns are floored at STICKY_FLOOR[X] for STICKY_WINDOW.
STICKY_FLOOR: dict[RiskTier, RiskTier] = {
    RiskTier.HIGH: RiskTier.MODERATE,
    RiskTier.IMMINENT: RiskTier.HIGH,
}
STICKY_WINDOW = timedelta(hours=72)

FOLLOW_UP_AFTER: dict[RiskTier, timedelta] = {
    RiskTier.MODERATE: timedelta(hours=24),
    RiskTier.HIGH: timedelta(hours=12),
    RiskTier.IMMINENT: timedelta(hours=12),
}

# A positive PHQ-9 item 9 floors risk at MODERATE for this long.
ASSESSMENT_FLOOR_WINDOW = timedelta(days=14)


@dataclass
class RiskState:
    peak_tier: RiskTier = RiskTier.NONE
    peak_at: datetime | None = None
    assessment_floor: RiskTier = RiskTier.NONE
    assessment_floor_at: datetime | None = None
    follow_up_due: datetime | None = None

    def floor(self, now: datetime) -> RiskTier:
        floor = RiskTier.NONE
        if self.peak_at and now - self.peak_at < STICKY_WINDOW:
            floor = max(floor, STICKY_FLOOR.get(self.peak_tier, RiskTier.NONE))
        if self.assessment_floor_at and now - self.assessment_floor_at < ASSESSMENT_FLOOR_WINDOW:
            floor = max(floor, self.assessment_floor)
        return floor


class RiskStateStore:
    """In-memory store. Replace with Redis-backed store (TDD §5.1) for production."""

    def __init__(self) -> None:
        self._states: dict[str, RiskState] = {}
        self._lock = threading.Lock()

    def get(self, user_id: str) -> RiskState:
        with self._lock:
            return self._states.setdefault(user_id, RiskState())

    def record_turn(self, user_id: str, tier: RiskTier, now: datetime | None = None) -> RiskState:
        now = now or datetime.now(UTC)
        with self._lock:
            state = self._states.setdefault(user_id, RiskState())
            in_window = state.peak_at and now - state.peak_at < STICKY_WINDOW
            if tier >= RiskTier.HIGH and (not in_window or tier >= state.peak_tier):
                state.peak_tier, state.peak_at = tier, now
            if tier in FOLLOW_UP_AFTER:
                due = now + FOLLOW_UP_AFTER[tier]
                # Never push an existing, earlier follow-up further out.
                if state.follow_up_due is None or due < state.follow_up_due:
                    state.follow_up_due = due
            return state

    def set_assessment_floor(
        self, user_id: str, tier: RiskTier, now: datetime | None = None
    ) -> None:
        now = now or datetime.now(UTC)
        with self._lock:
            state = self._states.setdefault(user_id, RiskState())
            state.assessment_floor, state.assessment_floor_at = tier, now
