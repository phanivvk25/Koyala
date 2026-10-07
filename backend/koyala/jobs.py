"""Background jobs. Run the SLA sweep every minute (e.g. from cron or a scheduler):

python -m koyala.jobs sweep-escalations
"""

from __future__ import annotations

import logging
import sys

from koyala.escalation import EscalationService, LogPager, StubPartner


def sweep_escalations() -> int:
    from koyala.main import _default_stores

    stores = _default_stores()
    service = EscalationService(stores.escalations, StubPartner(), LogPager())
    breached = service.sweep_overdue()
    print(f"{len(breached)} escalation(s) breached the connect SLA")
    return 0


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO)
    if argv[1:] == ["sweep-escalations"]:
        return sweep_escalations()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
