import base64
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from koyala.db.crypto import Crypto
from koyala.db.models import EscalationRow
from koyala.db.stores import SqlEscalationStore, make_session_factory
from koyala.escalation import (
    CONNECT_SLA,
    Channel,
    EscalationService,
    InMemoryEscalationStore,
    InvalidTransition,
    PartnerUnavailable,
    Status,
)
from koyala.main import create_app
from tests.conftest import sign_up
from tests.test_db import BACKENDS, _prepare_db

T0 = datetime(2026, 1, 1, tzinfo=UTC)


class FakePartner:
    def __init__(self, fail=False):
        self.fail = fail
        self.contexts = []

    def request_handoff(self, context):
        self.contexts.append(context)
        if self.fail:
            raise PartnerUnavailable("down")
        return f"ref-{len(self.contexts)}"


class FakePager:
    def __init__(self):
        self.pages = []

    def page(self, severity, message, escalation_id):
        self.pages.append((severity, escalation_id))


@pytest.fixture(params=["memory", *BACKENDS])
def store(request, tmp_path):
    if request.param == "memory":
        yield InMemoryEscalationStore()
        return
    eng = create_engine(_prepare_db(request.param, tmp_path))
    yield SqlEscalationStore(
        make_session_factory(eng), Crypto(base64.b64decode(Crypto.generate_key()))
    )
    eng.dispose()


def _service(store, fail=False):
    partner, pager = FakePartner(fail), FakePager()
    return EscalationService(store, partner, pager), partner, pager


# --- service + store contract ---------------------------------------------------------


def test_request_hands_over_minimum_context_and_pages(store):
    svc, partner, pager = _service(store)
    esc = svc.request("u1", Channel.CHAT, 3, ("SUI",), "te", callback_number="999", now=T0)
    assert esc.status is Status.REQUESTED and esc.partner_ref == "ref-1"
    ctx = partner.contexts[0]
    assert (ctx.risk_tier, ctx.categories, ctx.language) == (3, ("SUI",), "te")
    assert ctx.callback_number is None  # number only shared for call-backs
    assert not hasattr(ctx, "user_id")
    assert pager.pages == [("high", esc.id)]
    assert store.get(esc.id) == esc


def test_imminent_risk_pages_critical(store):
    svc, _, pager = _service(store)
    esc = svc.request("u1", Channel.CHAT, 4, (), "en", now=T0)
    assert pager.pages == [("critical", esc.id)]


def test_callback_number_round_trips(store):
    svc, partner, _ = _service(store)
    esc = svc.request("u1", Channel.CALLBACK, 3, (), "en", callback_number="+91 98765 43210")
    assert partner.contexts[0].callback_number == "+91 98765 43210"
    assert store.get(esc.id).callback_number == "+91 98765 43210"


def test_partner_failure_marks_failed_and_pages(store):
    svc, _, pager = _service(store, fail=True)
    esc = svc.request("u1", Channel.CHAT, 3, (), "en", now=T0)
    assert esc.status is Status.FAILED
    assert store.get(esc.id).status is Status.FAILED
    assert pager.pages == [("critical", esc.id)]


def test_repeat_request_returns_open_escalation(store):
    svc, partner, pager = _service(store)
    first = svc.request("u1", Channel.CHAT, 3, (), "en", now=T0)
    again = svc.request("u1", Channel.CHAT, 3, (), "en", now=T0 + timedelta(seconds=5))
    assert again.id == first.id
    assert len(partner.contexts) == 1 and len(pager.pages) == 1
    other = svc.request("u2", Channel.CHAT, 3, (), "en", now=T0)
    assert other.id != first.id


def test_status_transitions(store):
    svc, _, _ = _service(store)
    esc = svc.request("u1", Channel.CHAT, 3, (), "en", now=T0)
    esc = svc.update_status(esc.id, Status.CONNECTED, now=T0 + timedelta(minutes=2))
    assert esc.connected_at == T0 + timedelta(minutes=2)
    assert svc.update_status(esc.id, Status.CONNECTED).status is Status.CONNECTED  # idempotent
    with pytest.raises(InvalidTransition):
        svc.update_status(esc.id, Status.REQUESTED)
    esc = svc.update_status(esc.id, Status.CLOSED, now=T0 + timedelta(minutes=30))
    assert store.get(esc.id).closed_at == T0 + timedelta(minutes=30)
    with pytest.raises(KeyError):
        svc.update_status("missing", Status.CLOSED)
    # A closed escalation no longer blocks a new request.
    assert svc.request("u1", Channel.CHAT, 3, (), "en").id != esc.id


def test_sla_sweep_pages_once(store):
    svc, _, pager = _service(store)
    late = svc.request("u1", Channel.CHAT, 3, (), "en", now=T0)
    connected = svc.request("u2", Channel.CHAT, 3, (), "en", now=T0)
    svc.update_status(connected.id, Status.CONNECTED, now=T0 + timedelta(minutes=1))
    fresh = svc.request("u3", Channel.CHAT, 3, (), "en", now=T0 + CONNECT_SLA)
    pager.pages.clear()

    breached = svc.sweep_overdue(now=T0 + CONNECT_SLA + timedelta(seconds=1))
    assert [e.id for e in breached] == [late.id]
    assert pager.pages == [("critical", late.id)]
    assert store.get(late.id).sla_breached
    assert svc.sweep_overdue(now=T0 + CONNECT_SLA * 3) != []  # only `fresh` now
    assert {e.id for e in svc.sweep_overdue(now=T0 + CONNECT_SLA * 9)} == set()
    assert store.get(fresh.id).sla_breached


def test_callback_number_encrypted_at_rest(tmp_path):
    eng = create_engine(_prepare_db("sqlite", tmp_path))
    store = SqlEscalationStore(
        make_session_factory(eng), Crypto(base64.b64decode(Crypto.generate_key()))
    )
    svc, _, _ = _service(store)
    svc.request("u1", Channel.CALLBACK, 3, (), "en", callback_number="9876543210")
    with eng.connect() as conn:
        blob = conn.scalars(select(EscalationRow.callback_number_enc)).one()
    assert b"9876543210" not in blob


# --- API ---------------------------------------------------------------------------------


@pytest.fixture
def app_parts():
    partner, pager = FakePartner(), FakePager()
    client = TestClient(create_app(jwt_secret="s" * 48, partner=partner, pager=pager))
    client.headers.update(sign_up(client))
    return client, partner, pager


def test_api_request_uses_current_risk_tier(app_parts):
    client, partner, _ = app_parts
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    client.post(f"/v1/sessions/{sid}/messages", json={"text": "I want to kill myself"})
    r = client.post("/v1/escalations", json={"channel": "chat"})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "requested"
    assert {a["number"] for a in body["actions"]} >= {"14416", "112"}
    assert partner.contexts[0].risk_tier == 3
    got = client.get(f"/v1/escalations/{body['id']}").json()
    assert got["id"] == body["id"]


def test_api_partner_failure_still_shows_helplines():
    pager = FakePager()
    client = TestClient(
        create_app(jwt_secret="s" * 48, partner=FakePartner(fail=True), pager=pager)
    )
    client.headers.update(sign_up(client))
    body = client.post("/v1/escalations", json={}).json()
    assert body["status"] == "failed"
    assert "helplines" in body["text"]
    assert any(a["number"] == "112" for a in body["actions"])
    assert pager.pages and pager.pages[0][0] == "critical"


def test_api_callback_validation(app_parts):
    client, _, _ = app_parts
    assert client.post("/v1/escalations", json={"channel": "callback"}).status_code == 422
    bad = {"channel": "callback", "callback_number": "call me"}
    assert client.post("/v1/escalations", json=bad).status_code == 422


def test_api_escalations_private_to_user(app_parts):
    client, _, _ = app_parts
    esc = client.post("/v1/escalations", json={}).json()
    other = sign_up(client)
    assert client.get(f"/v1/escalations/{esc['id']}", headers=other).status_code == 404
    assert client.post(f"/v1/escalations/{esc['id']}/cancel", headers=other).status_code == 404
    assert client.post(f"/v1/escalations/{esc['id']}/cancel").json()["status"] == "closed"


def test_partner_callback_requires_token(app_parts, monkeypatch):
    client, _, _ = app_parts
    esc = client.post("/v1/escalations", json={}).json()
    url = f"/v1/partner/escalations/{esc['id']}/status"
    monkeypatch.delenv("KOYALA_PARTNER_TOKEN", raising=False)
    assert client.post(url, json={"status": "connected"}).status_code == 503
    monkeypatch.setenv("KOYALA_PARTNER_TOKEN", "partner-secret")
    assert client.post(url, json={"status": "connected"}).status_code == 401
    wrong = {"X-Partner-Token": "nope"}
    assert client.post(url, json={"status": "connected"}, headers=wrong).status_code == 401
    ok = {"X-Partner-Token": "partner-secret"}
    assert client.post(url, json={"status": "connected"}, headers=ok).status_code == 204
    assert client.get(f"/v1/escalations/{esc['id']}").json()["status"] == "connected"
    assert client.post(url, json={"status": "requested"}, headers=ok).status_code == 409
    missing = "/v1/partner/escalations/nope/status"
    assert client.post(missing, json={"status": "closed"}, headers=ok).status_code == 404


def test_escalations_require_auth():
    client = TestClient(create_app(jwt_secret="s" * 48))
    assert client.post("/v1/escalations", json={}).status_code == 401
