"""Background jobs.

python -m koyala.jobs sweep-escalations   # every minute
python -m koyala.jobs send-follow-ups     # every 5 minutes
python -m koyala.jobs scheduler           # both, on that cadence (local Docker)
"""

from __future__ import annotations

import logging
import sys

from koyala.escalation import EscalationService, LogPager, StubPartner


def _stores():
    from koyala.main import _default_stores

    return _default_stores()


def sweep_escalations(stores=None) -> int:
    stores = stores or _stores()
    service = EscalationService(stores.escalations, StubPartner(), LogPager())
    breached = service.sweep_overdue()
    print(f"{len(breached)} escalation(s) breached the connect SLA")
    return 0


def send_follow_ups(stores=None) -> int:
    from koyala.followups import FollowUpService, LogNotifier

    stores = stores or _stores()
    result = FollowUpService(stores.risk_states, stores.tracking, LogNotifier(), LogPager()).run()
    print(f"{result.sent} follow-up(s) sent, {result.paged} unanswered high-risk check-in(s) paged")
    return 0


def scheduler(tick_seconds: int = 60) -> int:
    """Run both jobs forever: escalation sweep every tick, follow-ups every 5 ticks.

    For local Docker and small deployments; production should use the
    platform's scheduler (Cloud Scheduler, EventBridge, CronJob) instead.
    """
    import time

    log = logging.getLogger("koyala.jobs")
    stores = _stores()  # one connection pool for the life of the scheduler
    tick = 0
    while True:
        for name, job, every in (
            ("sweep-escalations", sweep_escalations, 1),
            ("send-follow-ups", send_follow_ups, 5),
        ):
            if tick % every == 0:
                try:
                    job(stores)
                except Exception:
                    # Keep the scheduler alive; the next tick retries.
                    log.exception("job %s failed", name)
        tick += 1
        time.sleep(tick_seconds)


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO)
    if argv[1:] == ["sweep-escalations"]:
        return sweep_escalations()
    if argv[1:] == ["send-follow-ups"]:
        return send_follow_ups()
    if argv[1:] == ["scheduler"]:
        return scheduler()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
