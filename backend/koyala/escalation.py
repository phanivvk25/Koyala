"""Human escalation: "Talk to a counsellor now" (Clinical Safety Protocol §7, TDD §5.5).

A request is recorded, handed to the crisis partner, and tracked against the
connect SLA. The on-call clinical lead is paged when the partner can't take
the request or the SLA is missed. Only the minimum necessary context is
shared with the partner (risk tier, categories, language, channel; the
callback number only for call-backs).

`StubPartner` and `LogPager` are placeholders until a crisis partner is
contracted (BRD BR-04).
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol

log = logging.getLogger(__name__)

CONNECT_SLA = timedelta(minutes=5)
# Recent peak risk counts towards the tier reported to the partner.
STICKY_LOOKBACK = timedelta(hours=72)


class Channel(StrEnum):
    CHAT = "chat"
    CALLBACK = "callback"


class Status(StrEnum):
    REQUESTED = "requested"  # partner accepted, waiting for a counsellor
    CONNECTED = "connected"
    CLOSED = "closed"
    FAILED = "failed"  # partner could not take it; user shown helplines, on-call paged


OPEN_STATUSES = frozenset({Status.REQUESTED})


@dataclass(frozen=True)
class Escalation:
    id: str
    user_id: str
    channel: Channel
    risk_tier: int
    categories: tuple[str, ...]
    language: str
    status: Status
    created_at: datetime
    callback_number: str | None = None
    partner_ref: str | None = None
    connected_at: datetime | None = None
    closed_at: datetime | None = None
    sla_breached: bool = False


@dataclass(frozen=True)
class PartnerContext:
    """Exactly what is shared with the crisis partner."""

    escalation_id: str
    channel: Channel
    risk_tier: int
    categories: tuple[str, ...]
    language: str
    callback_number: str | None


class PartnerUnavailable(Exception):
    pass


class CrisisPartner(Protocol):
    def request_handoff(self, context: PartnerContext) -> str:
        """Hand over to the partner; return the partner's reference."""
        ...


class Pager(Protocol):
    def page(self, severity: str, message: str, escalation_id: str) -> None: ...


class StubPartner:
    """Accepts every request; replace with the contracted partner's API."""

    def request_handoff(self, context: PartnerContext) -> str:
        log.warning(
            "StubPartner: no crisis partner configured (escalation %s)", context.escalation_id
        )
        return f"stub-{context.escalation_id[:8]}"


class LogPager:
    """Logs pages; replace with the on-call paging service."""

    def page(self, severity: str, message: str, escalation_id: str) -> None:
        log.critical("PAGE[%s] escalation=%s %s", severity, escalation_id, message)


class EscalationStore(Protocol):
    def save(self, escalation: Escalation) -> None: ...

    def get(self, escalation_id: str) -> Escalation | None: ...

    def open_before(self, cutoff: datetime) -> list[Escalation]:
        """Open escalations created before cutoff and not yet marked breached."""
        ...

    def open_for_user(self, user_id: str) -> Escalation | None: ...


class InMemoryEscalationStore:
    def __init__(self) -> None:
        self._items: dict[str, Escalation] = {}
        self._lock = threading.Lock()

    def save(self, escalation: Escalation) -> None:
        with self._lock:
            self._items[escalation.id] = escalation

    def get(self, escalation_id: str) -> Escalation | None:
        with self._lock:
            return self._items.get(escalation_id)

    def open_before(self, cutoff: datetime) -> list[Escalation]:
        with self._lock:
            return [
                e
                for e in self._items.values()
                if e.status in OPEN_STATUSES and e.created_at < cutoff and not e.sla_breached
            ]

    def open_for_user(self, user_id: str) -> Escalation | None:
        with self._lock:
            open_ = [
                e
                for e in self._items.values()
                if e.user_id == user_id and e.status in OPEN_STATUSES
            ]
        return max(open_, key=lambda e: e.created_at, default=None)


class InvalidTransition(Exception):
    pass


_TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.REQUESTED: frozenset({Status.CONNECTED, Status.CLOSED, Status.FAILED}),
    Status.CONNECTED: frozenset({Status.CLOSED}),
    Status.CLOSED: frozenset(),
    Status.FAILED: frozenset({Status.CLOSED}),
}


class EscalationService:
    def __init__(self, store: EscalationStore, partner: CrisisPartner, pager: Pager) -> None:
        self._store = store
        self._partner = partner
        self._pager = pager

    def request(
        self,
        user_id: str,
        channel: Channel,
        risk_tier: int,
        categories: tuple[str, ...],
        language: str,
        callback_number: str | None = None,
        now: datetime | None = None,
    ) -> Escalation:
        now = now or datetime.now(UTC)
        existing = self._store.open_for_user(user_id)
        if existing is not None:
            # Repeated taps must not create duplicate requests or pages.
            return existing
        esc = Escalation(
            id=uuid.uuid4().hex,
            user_id=user_id,
            channel=channel,
            risk_tier=risk_tier,
            categories=categories,
            language=language,
            status=Status.REQUESTED,
            created_at=now,
            callback_number=callback_number if channel is Channel.CALLBACK else None,
        )
        # Persist before calling out, so the request exists even if the partner hangs.
        self._store.save(esc)
        context = PartnerContext(
            escalation_id=esc.id,
            channel=esc.channel,
            risk_tier=esc.risk_tier,
            categories=esc.categories,
            language=esc.language,
            callback_number=esc.callback_number,
        )
        try:
            ref = self._partner.request_handoff(context)
        except Exception:
            log.exception("crisis partner handoff failed for escalation %s", esc.id)
            esc = replace(esc, status=Status.FAILED)
            self._store.save(esc)
            self._pager.page("critical", "crisis partner handoff failed", esc.id)
            return esc
        esc = replace(esc, partner_ref=ref)
        self._store.save(esc)
        severity = "critical" if risk_tier >= 4 else "high"
        self._pager.page(severity, f"counsellor handoff requested (tier {risk_tier})", esc.id)
        return esc

    def get_for_user(self, user_id: str, escalation_id: str) -> Escalation | None:
        esc = self._store.get(escalation_id)
        return esc if esc is not None and esc.user_id == user_id else None

    def update_status(
        self, escalation_id: str, status: Status, now: datetime | None = None
    ) -> Escalation:
        now = now or datetime.now(UTC)
        esc = self._store.get(escalation_id)
        if esc is None:
            raise KeyError(escalation_id)
        if status == esc.status:
            return esc
        if status not in _TRANSITIONS[esc.status]:
            raise InvalidTransition(f"{esc.status} -> {status}")
        changes: dict = {"status": status}
        if status is Status.CONNECTED:
            changes["connected_at"] = now
        if status is Status.CLOSED:
            changes["closed_at"] = now
        esc = replace(esc, **changes)
        self._store.save(esc)
        return esc

    def sweep_overdue(self, now: datetime | None = None) -> list[Escalation]:
        """Page on-call for requests not connected within the SLA. Run every minute."""
        now = now or datetime.now(UTC)
        breached = []
        for esc in self._store.open_before(now - CONNECT_SLA):
            esc = replace(esc, sla_breached=True)
            self._store.save(esc)
            self._pager.page("critical", f"counsellor not connected within {CONNECT_SLA}", esc.id)
            breached.append(esc)
        return breached
