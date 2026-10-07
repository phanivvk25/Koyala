import base64

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select

from koyala.db import models
from koyala.db.crypto import Crypto
from koyala.main import create_app
from tests.test_db import BACKENDS, _prepare_db, _sql_stores

SECRET = "s" * 48


@pytest.fixture(params=["memory", *BACKENDS])
def env(request, tmp_path):
    if request.param == "memory":
        yield TestClient(create_app(jwt_secret=SECRET)), None
        return
    url = _prepare_db(request.param, tmp_path)
    crypto = Crypto(base64.b64decode(Crypto.generate_key()))
    yield TestClient(create_app(stores=_sql_stores(url, crypto), jwt_secret=SECRET)), url


def _account(client):
    tokens = client.post("/v1/auth/anonymous").json()
    return tokens, {"Authorization": f"Bearer {tokens['access_token']}"}


def _fill(client, h):
    sid = client.post("/v1/sessions", json={"language": "te"}, headers=h).json()["session_id"]
    client.post(f"/v1/sessions/{sid}/messages", json={"text": "exam stress"}, headers=h)
    client.post(f"/v1/sessions/{sid}/messages", json={"text": "I want to kill myself"}, headers=h)
    client.post("/v1/mood", json={"score": 2, "note": "tired"}, headers=h)
    client.post("/v1/journal", json={"text": "public entry"}, headers=h)
    client.post("/v1/journal", json={"text": "secret entry", "private": True}, headers=h)
    client.post("/v1/assessments", json={"instrument": "GAD7", "item_scores": [2] * 7}, headers=h)
    client.put("/v1/safety/plan", json={"support_contacts": ["Amma"]}, headers=h)
    client.post(
        "/v1/escalations",
        json={"channel": "callback", "callback_number": "+91 98765 43210"},
        headers=h,
    )
    return sid


def test_export_contains_everything(env):
    client, _ = env
    tokens, h = _account(client)
    sid = _fill(client, h)
    r = client.get("/v1/privacy/export", headers=h)
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert r.headers["cache-control"] == "no-store"
    data = r.json()
    assert data["user"]["id"] == tokens["user_id"]
    [session] = data["chat_sessions"]
    assert session["id"] == sid and session["language"] == "te"
    assert [m["content"] for m in session["messages"] if m["role"] == "user"] == [
        "exam stress",
        "I want to kill myself",
    ]
    assert data["mood_logs"][0]["note"] == "tired"
    assert {(j["text"], j["private"]) for j in data["journal"]} == {
        ("public entry", False),
        ("secret entry", True),
    }
    assert data["assessments"][0]["instrument"] == "GAD7"
    assert data["safety_plan"]["support_contacts"] == ["Amma"]
    assert data["risk_state"]["peak_tier"] == 3
    assert data["escalations"][0]["callback_number"] == "+91 98765 43210"


def test_export_is_per_user(env):
    client, _ = env
    _, a = _account(client)
    _fill(client, a)
    _, b = _account(client)
    data = client.get("/v1/privacy/export", headers=b).json()
    assert data["chat_sessions"] == [] and data["journal"] == [] and data["escalations"] == []


def test_delete_account_erases_everything(env):
    client, url = env
    tokens, h = _account(client)
    _fill(client, h)
    other_tokens, other = _account(client)
    _fill(client, other)

    assert client.post("/v1/privacy/delete-account", json={}, headers=h).status_code == 422
    r = client.post("/v1/privacy/delete-account", json={"confirm": "DELETE"}, headers=h)
    assert r.status_code == 204

    # Old access and refresh tokens stop working immediately.
    assert client.get("/v1/mood", headers=h).status_code == 401
    assert client.get("/v1/privacy/export", headers=h).status_code == 401
    refresh = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 401

    # The other user is untouched.
    assert len(client.get("/v1/journal", headers=other).json()) == 2

    if url:
        eng = create_engine(url)
        with eng.connect() as conn:
            for model in (
                models.ChatSession,
                models.UserRecord,
                models.RiskEvent,
                models.RiskStateRow,
                models.EscalationRow,
                models.RefreshToken,
            ):
                gone = conn.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.user_id == tokens["user_id"])
                )
                kept = conn.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.user_id == other_tokens["user_id"])
                )
                assert gone == 0, model.__tablename__
                assert kept > 0, model.__tablename__
            assert conn.scalar(select(func.count()).select_from(models.Message)) > 0
            assert (
                conn.scalar(
                    select(func.count())
                    .select_from(models.User)
                    .where(models.User.id == tokens["user_id"])
                )
                == 0
            )
        eng.dispose()


def test_privacy_requires_auth(env):
    client, _ = env
    assert client.get("/v1/privacy/export").status_code == 401
    assert client.post("/v1/privacy/delete-account", json={"confirm": "DELETE"}).status_code == 401
