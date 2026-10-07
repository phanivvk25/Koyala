"""Follow-up check-ins after elevated risk (Clinical Safety Protocol §9).

`FollowUpService.run()` is meant to run every few minutes
(`python -m koyala.jobs send-follow-ups`). It:

1. sends a check-in to every user whose follow-up is due (24 h after tier 2,
   12 h after tier >= 3): an in-app message plus a push notification whose
   text never mentions risk or mental health;
2. pages on-call once for any tier >= 3 check-in still unanswered after 24 h,
   so a human can reach out (with consent, per protocol).

`LogNotifier` is a placeholder until push notifications (FCM/APNs) exist.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from koyala.escalation import Pager
from koyala.safety import crisis
from koyala.safety.models import RiskTier
from koyala.safety.risk_state import STICKY_WINDOW, RiskStateStore
from koyala.tracking import RecordKind, TrackingStore

log = logging.getLogger(__name__)

NO_RESPONSE_AFTER = timedelta(hours=24)
# Only look this far back for unanswered check-ins, so the scan stays bounded.
NO_RESPONSE_WINDOW = timedelta(days=3)

PUSH_TITLE = "Koyala"
PUSH_BODY = "Checking in on you. Tap to open."

PENDING = "pending"
ACKNOWLEDGED = "acknowledged"


class Notifier(Protocol):
    def notify(self, user_id: str, title: str, body: str) -> None: ...


class LogNotifier:
    def notify(self, user_id: str, title: str, body: str) -> None:
        log.info("push to %s: %s", user_id, title)


@dataclass(frozen=True)
class RunResult:
    sent: int
    paged: int


class FollowUpService:
    def __init__(
        self,
        risk_states: RiskStateStore,
        tracking: TrackingStore,
        notifier: Notifier,
        pager: Pager,
    ) -> None:
        self._risk = risk_states
        self._tracking = tracking
        self._notifier = notifier
        self._pager = pager

    def run(self, now: datetime | None = None) -> RunResult:
        now = now or datetime.now(UTC)
        return RunResult(sent=self._send_due(now), paged=self._page_unanswered(now))

    def _send_due(self, now: datetime) -> int:
        sent = 0
        for user_id, state in self._risk.due_follow_ups(now):
            tier = RiskTier.MODERATE
            if state.peak_at and now - state.peak_at < STICKY_WINDOW:
                tier = max(tier, state.peak_tier)
            msg = crisis.follow_up_message(tier)
            self._tracking.add(
                user_id,
                RecordKind.CHECK_IN,
                {
                    "text": msg.text,
                    "template_id": msg.template_id,
                    "tier": int(tier),
                    "status": PENDING,
                    "paged": False,
                },
                now=now,
            )
            try:
                self._notifier.notify(user_id, PUSH_TITLE, PUSH_BODY)
            except Exception:
                # The in-app check-in is already stored; a failed push must not
                # cause a duplicate on the next run.
                log.exception("push notification failed for follow-up")
            self._risk.clear_follow_up(user_id, state.follow_up_due)
            sent += 1
        return sent

    def _page_unanswered(self, now: datetime) -> int:
        paged = 0
        end = now - NO_RESPONSE_AFTER
        for user_id, rec in self._tracking.list_window(
            RecordKind.CHECK_IN, end - NO_RESPONSE_WINDOW, end
        ):
            p = rec.payload
            if p.get("status") != PENDING or p.get("paged") or p.get("tier", 0) < RiskTier.HIGH:
                continue
            self._pager.page("high", "no response to high-risk follow-up check-in", rec.id)
            self._tracking.update(user_id, RecordKind.CHECK_IN, rec.id, {**p, "paged": True})
            paged += 1
        return paged
