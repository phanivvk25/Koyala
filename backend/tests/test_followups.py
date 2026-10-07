import base64
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from koyala.db.crypto import Crypto
from koyala.db.stores import SqlRiskStateStore, SqlTrackingStore, make_session_factory
from koyala.followups import ACKNOWLEDGED, PENDING, PUSH_BODY, FollowUpService
from koyala.main import create_app
from koyala.safety.models import RiskTier
from koyala.safety.risk_state import InMemoryRiskStateStore
from koyala.tracking import InMemoryTrackingStore, RecordKind
from tests.conftest import sign_up
from tests.test_db import BACKENDS, _prepare_db

T0 = datetime(2026, 1, 1, tzinfo=UTC)
H = timedelta(hours=1)


class FakeNotifier:
    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []

    def notify(self, user_id, title, body):
        self.sent.append((user_id, body))
        if self.fail:
            raise RuntimeError("push down")


class FakePager:
    def __init__(self):
        self.pages = []

    def page(self, severity, message, ref):
        self.pages.append((severity, ref))


@pytest.fixture(params=["memory", *BACKENDS])
def stores(request, tmp_path):
    if request.param == "memory":
        yield InMemoryRiskStateStore(), InMemoryTrackingStore()
        return
    eng = create_engine(_prepare_db(request.param, tmp_path))
    factory = make_session_factory(eng)
    crypto = Crypto(base64.b64decode(Crypto.generate_key()))
    yield SqlRiskStateStore(factory, crypto), SqlTrackingStore(factory, crypto)
    eng.dispose()


def _service(stores, notifier=None):
    risk, tracking = stores
    notifier, pager = notifier or FakeNotifier(), FakePager()
    return FollowUpService(risk, tracking, notifier, pager), notifier, pager


def test_follow_up_sent_when_due_and_only_once(stores):
    risk, tracking = stores
    svc, notifier, _ = _service(stores)
    risk.record_turn("mod", RiskTier.MODERATE, T0)  # due T0+24h
    risk.record_turn("high", RiskTier.HIGH, T0)  # due T0+12h

    assert svc.run(T0 + 11 * H).sent == 0
    assert svc.run(T0 + 13 * H).sent == 1
    [high] = tracking.list("high", RecordKind.CHECK_IN)
    assert high.payload["tier"] == 3 and high.payload["status"] == PENDING
    assert high.payload["template_id"].startswith("followup_t3")
    assert tracking.list("mod", RecordKind.CHECK_IN) == []

    assert svc.run(T0 + 25 * H).sent == 1
    [mod] = tracking.list("mod", RecordKind.CHECK_IN)
    assert mod.payload["tier"] == 2 and mod.payload["template_id"].startswith("followup_t2")

    assert svc.run(T0 + 30 * H).sent == 0  # nothing re-sent
    assert {u for u, _ in notifier.sent} == {"high", "mod"}
    assert all(body == PUSH_BODY for _, body in notifier.sent)


def test_push_failure_does_not_cause_duplicates(stores):
    risk, tracking = stores
    svc, _, _ = _service(stores, FakeNotifier(fail=True))
    risk.record_turn("u", RiskTier.HIGH, T0)
    assert svc.run(T0 + 13 * H).sent == 1
    assert svc.run(T0 + 14 * H).sent == 0
    assert len(tracking.list("u", RecordKind.CHECK_IN)) == 1


def test_newer_follow_up_schedule_not_cleared(stores):
    risk, _ = stores
    risk.record_turn("u", RiskTier.MODERATE, T0)
    due = risk.get("u").follow_up_due
    risk.clear_follow_up("u", due - H)  # stale value: no-op
    assert risk.get("u").follow_up_due == due
    risk.clear_follow_up("u", due)
    assert risk.get("u").follow_up_due is None


def test_unanswered_high_risk_check_in_pages_once(stores):
    risk, tracking = stores
    svc, _, pager = _service(stores)
    risk.record_turn("high", RiskTier.HIGH, T0)
    risk.record_turn("mod", RiskTier.MODERATE, T0)
    risk.record_turn("acked", RiskTier.HIGH, T0)
    svc.run(T0 + 25 * H)  # sends all three
    [acked] = tracking.list("acked", RecordKind.CHECK_IN)
    tracking.update(
        "acked", RecordKind.CHECK_IN, acked.id, {**acked.payload, "status": ACKNOWLEDGED}
    )

    assert svc.run(T0 + 40 * H).paged == 0  # not yet 24 h unanswered
    result = svc.run(T0 + 50 * H)
    [high] = tracking.list("high", RecordKind.CHECK_IN)
    assert result.paged == 1 and pager.pages == [("high", high.id)]
    assert high.payload["paged"] is True
    assert svc.run(T0 + 51 * H).paged == 0  # paged only once


def test_tracking_update_is_per_user(stores):
    _, tracking = stores
    rec = tracking.add("u1", RecordKind.CHECK_IN, {"status": PENDING}, now=T0)
    assert tracking.update("u2", RecordKind.CHECK_IN, rec.id, {"status": "x"}) is None
    assert tracking.update("u1", RecordKind.CHECK_IN, "nope", {"status": "x"}) is None
    assert tracking.list("u1", RecordKind.CHECK_IN)[0].payload == {"status": PENDING}


# --- API ---------------------------------------------------------------------------------


def test_check_in_api_flow():
    app = create_app(jwt_secret="s" * 48)
    client = TestClient(app)
    h = sign_up(client)
    sid = client.post("/v1/sessions", json={}, headers=h).json()["session_id"]
    client.post(f"/v1/sessions/{sid}/messages", json={"text": "I want to kill myself"}, headers=h)
    assert client.get("/v1/check-ins", headers=h).json() == []

    svc = FollowUpService(app.state.risk_states, app.state.tracking, FakeNotifier(), FakePager())
    assert svc.run(datetime.now(UTC) + 13 * H).sent == 1

    [ci] = client.get("/v1/check-ins", headers=h).json()
    assert ci["status"] == PENDING
    assert {a["kind"] for a in ci["actions"]} >= {"call", "handoff"}

    other = sign_up(client)
    assert client.post(f"/v1/check-ins/{ci['id']}/ack", headers=other).status_code == 404
    acked = client.post(f"/v1/check-ins/{ci['id']}/ack", headers=h).json()
    assert acked["status"] == ACKNOWLEDGED
    assert client.get("/v1/check-ins", headers=h).json() == []
    assert len(client.get("/v1/check-ins", params={"pending": False}, headers=h).json()) == 1

    export = client.get("/v1/privacy/export", headers=h).json()
    assert export["check_ins"][0]["status"] == ACKNOWLEDGED


def test_check_ins_require_auth():
    client = TestClient(create_app(jwt_secret="s" * 48))
    assert client.get("/v1/check-ins").status_code == 401
