import base64
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from koyala.db.crypto import Crypto
from koyala.db.models import UserRecord
from koyala.db.stores import SqlTrackingStore, make_session_factory
from koyala.main import create_app
from koyala.tracking import InMemoryTrackingStore, RecordKind
from tests.conftest import sign_up
from tests.test_db import BACKENDS, _prepare_db

T0 = datetime(2026, 1, 1, tzinfo=UTC)
K = RecordKind


@pytest.fixture(params=["memory", *BACKENDS])
def store(request, tmp_path):
    if request.param == "memory":
        yield InMemoryTrackingStore()
        return
    eng = create_engine(_prepare_db(request.param, tmp_path))
    crypto = Crypto(base64.b64decode(Crypto.generate_key()))
    yield SqlTrackingStore(make_session_factory(eng), crypto)
    eng.dispose()


# --- store contract ------------------------------------------------------------


def test_add_and_list_newest_first(store):
    store.add("u1", K.MOOD, {"score": 2}, now=T0)
    store.add("u1", K.MOOD, {"score": 4}, now=T0 + timedelta(hours=1))
    store.add("u1", K.JOURNAL, {"text": "x"}, now=T0)
    moods = store.list("u1", K.MOOD)
    assert [r.payload["score"] for r in moods] == [4, 2]
    assert moods[0].created_at == T0 + timedelta(hours=1)
    assert len(store.list("u1", K.JOURNAL)) == 1


def test_list_since_and_limit(store):
    for i in range(5):
        store.add("u1", K.MOOD, {"score": i + 1}, now=T0 + timedelta(days=i))
    since = store.list("u1", K.MOOD, since=T0 + timedelta(days=3))
    assert [r.payload["score"] for r in since] == [5, 4]
    assert len(store.list("u1", K.MOOD, limit=2)) == 2


def test_records_are_per_user(store):
    store.add("u1", K.JOURNAL, {"text": "mine"}, now=T0)
    assert store.list("u2", K.JOURNAL) == []
    rec = store.list("u1", K.JOURNAL)[0]
    assert not store.delete("u2", K.JOURNAL, rec.id)  # can't delete another user's
    assert store.delete("u1", K.JOURNAL, rec.id)
    assert store.list("u1", K.JOURNAL) == []
    assert not store.delete("u1", K.JOURNAL, rec.id)


def test_private_flag_round_trips(store):
    store.add("u1", K.JOURNAL, {"text": "secret"}, private=True, now=T0)
    assert store.list("u1", K.JOURNAL)[0].private is True


def test_put_single_replaces(store):
    store.put_single("u1", K.SAFETY_PLAN, {"warning_signs": ["a"]}, now=T0)
    store.put_single("u1", K.SAFETY_PLAN, {"warning_signs": ["b"]}, now=T0 + timedelta(1))
    plans = store.list("u1", K.SAFETY_PLAN)
    assert len(plans) == 1 and plans[0].payload == {"warning_signs": ["b"]}


def test_unicode_payload(store):
    store.add("u1", K.JOURNAL, {"text": "ఈ రోజు బాగుంది — आज अच्छा दिन"}, now=T0)
    assert store.list("u1", K.JOURNAL)[0].payload["text"] == "ఈ రోజు బాగుంది — आज अच्छा दिन"


def test_payload_encrypted_at_rest(tmp_path):
    eng = create_engine(_prepare_db("sqlite", tmp_path))
    store = SqlTrackingStore(
        make_session_factory(eng), Crypto(base64.b64decode(Crypto.generate_key()))
    )
    store.add("u1", K.JOURNAL, {"text": "I feel anxious about my exams"}, now=T0)
    with eng.connect() as conn:
        blob = conn.scalars(select(UserRecord.payload_enc)).one()
    assert b"anxious" not in blob


# --- API -------------------------------------------------------------------------


@pytest.fixture
def client():
    c = TestClient(create_app(jwt_secret="s" * 48))
    c.headers.update(sign_up(c))
    return c


def test_mood_log_and_list(client):
    r = client.post(
        "/v1/mood",
        json={"score": 2, "emotions": ["anxious"], "factors": {"sleep_hours": 5.5}, "note": "ok"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["score"] == 2 and body["factors"]["sleep_hours"] == 5.5
    assert body["support"] is None
    listed = client.get("/v1/mood").json()
    assert [m["id"] for m in listed] == [body["id"]]


@pytest.mark.parametrize(
    "payload",
    [
        {"score": 0},
        {"score": 6},
        {"score": 3, "factors": {"sleep_hours": 30}},
        {"score": 3, "emotions": ["x"] * 11},
    ],
)
def test_mood_validation(client, payload):
    assert client.post("/v1/mood", json=payload).status_code == 422


def test_mood_note_is_risk_screened(client):
    r = client.post("/v1/mood", json={"score": 1, "note": "I want to kill myself"}).json()
    assert r["support"]["type"] == "crisis"
    assert any(a["kind"] == "handoff" for a in r["support"]["actions"])
    # The elevated risk carries into the next chat turn (sticky floor).
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    turn = client.post(f"/v1/sessions/{sid}/messages", json={"text": "hi"}).json()
    assert turn["risk_tier"] >= 2


def test_journal_crud_and_screening(client):
    r = client.post("/v1/journal", json={"text": "I wish I could just disappear"}).json()
    assert r["support"]["risk_tier"] == 2
    p = client.post("/v1/journal", json={"text": "I want to kill myself", "private": True}).json()
    assert p["private"] is True and p["support"] is None  # private: not processed
    listed = client.get("/v1/journal").json()
    assert {e["id"] for e in listed} == {r["id"], p["id"]}
    assert client.delete(f"/v1/journal/{r['id']}").status_code == 204
    assert client.delete(f"/v1/journal/{r['id']}").status_code == 404
    assert [e["id"] for e in client.get("/v1/journal").json()] == [p["id"]]


def test_journal_isolated_between_users(client):
    entry = client.post("/v1/journal", json={"text": "mine"}).json()
    other = sign_up(client)
    assert client.get("/v1/journal", headers=other).json() == []
    assert client.delete(f"/v1/journal/{entry['id']}", headers=other).status_code == 404


def test_assessments_are_persisted(client):
    a = client.post("/v1/assessments", json={"instrument": "PHQ9", "item_scores": [2] * 9})
    client.post("/v1/assessments", json={"instrument": "GAD7", "item_scores": [1] * 7})
    history = client.get("/v1/assessments").json()
    assert len(history) == 2
    phq = client.get("/v1/assessments", params={"instrument": "PHQ9"}).json()
    assert [h["id"] for h in phq] == [a.json()["id"]]
    assert phq[0]["total"] == 18 and phq[0]["band"] == "moderately_severe"


def test_safety_plan(client):
    assert client.get("/v1/safety/plan").json()["updated_at"] is None
    plan = {"warning_signs": ["can't sleep"], "support_contacts": ["Amma"]}
    r = client.put("/v1/safety/plan", json=plan)
    assert r.status_code == 200 and r.json()["warning_signs"] == ["can't sleep"]
    got = client.get("/v1/safety/plan").json()
    assert got["support_contacts"] == ["Amma"] and got["updated_at"] is not None
    assert client.put("/v1/safety/plan", json={"warning_signs": [""]}).status_code == 422


def test_tracking_requires_auth():
    c = TestClient(create_app(jwt_secret="s" * 48))
    for method, path in [
        ("get", "/v1/mood"),
        ("post", "/v1/journal"),
        ("get", "/v1/assessments"),
        ("get", "/v1/safety/plan"),
    ]:
        assert getattr(c, method)(path).status_code == 401
