from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from koyala.auth.refresh import (
    REFRESH_TTL,
    InMemoryAuthStore,
    InvalidRefreshToken,
    RefreshTokenReused,
)
from koyala.auth.tokens import InvalidToken, TokenService
from koyala.db.models import RefreshToken
from koyala.db.stores import SqlAuthStore, make_session_factory
from koyala.main import create_app
from tests.test_db import BACKENDS, _prepare_db

SECRET = "s" * 48
T0 = datetime(2026, 1, 1, tzinfo=UTC)


# --- access tokens -------------------------------------------------------------


def test_access_token_round_trip():
    svc = TokenService(SECRET)
    assert svc.verify_access(svc.issue_access("anon_1")) == "anon_1"


def test_expired_access_token_rejected():
    svc = TokenService(SECRET)
    old = svc.issue_access("anon_1", now=datetime.now(UTC) - timedelta(hours=1))
    with pytest.raises(InvalidToken):
        svc.verify_access(old)


@pytest.mark.parametrize(
    "token",
    [
        # Wrong signature
        TokenService("t" * 48).issue_access("anon_1"),
        # alg=none
        jwt.encode({"sub": "anon_1"}, None, algorithm="none"),
        # Not an access token
        jwt.encode(
            {
                "sub": "a",
                "iss": "koyala",
                "typ": "refresh",
                "iat": T0,
                "exp": T0 + REFRESH_TTL * 99,
            },
            SECRET,
            algorithm="HS256",
        ),
        "garbage",
    ],
)
def test_forged_or_wrong_tokens_rejected(token):
    with pytest.raises(InvalidToken):
        TokenService(SECRET).verify_access(token)


def test_short_secret_rejected():
    with pytest.raises(ValueError):
        TokenService("too-short")


# --- refresh tokens (same contract for both stores) -----------------------------


@pytest.fixture(params=["memory", *BACKENDS])
def store(request, tmp_path):
    if request.param == "memory":
        yield InMemoryAuthStore()
        return
    import base64

    from koyala.db.crypto import Crypto

    eng = create_engine(_prepare_db(request.param, tmp_path))
    yield SqlAuthStore(make_session_factory(eng), Crypto(base64.b64decode(Crypto.generate_key())))
    eng.dispose()


def test_rotation_issues_new_token_and_consumes_old(store):
    user = store.create_anonymous_user()
    t1 = store.issue_refresh(user, now=T0)
    uid, t2 = store.rotate(t1, now=T0)
    assert uid == user and t2 != t1
    uid, _ = store.rotate(t2, now=T0)
    assert uid == user


def test_reuse_revokes_whole_family(store):
    user = store.create_anonymous_user()
    t1 = store.issue_refresh(user, now=T0)
    _, t2 = store.rotate(t1, now=T0)
    with pytest.raises(RefreshTokenReused):
        store.rotate(t1, now=T0)  # attacker replays the old token
    with pytest.raises(InvalidRefreshToken):
        store.rotate(t2, now=T0)  # legitimate holder is logged out too


def test_other_families_unaffected_by_reuse(store):
    user = store.create_anonymous_user()
    phone = store.issue_refresh(user, now=T0)
    laptop = store.issue_refresh(user, now=T0)
    _, _ = store.rotate(phone, now=T0)
    with pytest.raises(RefreshTokenReused):
        store.rotate(phone, now=T0)
    store.rotate(laptop, now=T0)


def test_expired_refresh_token_rejected(store):
    user = store.create_anonymous_user()
    t1 = store.issue_refresh(user, now=T0)
    with pytest.raises(InvalidRefreshToken):
        store.rotate(t1, now=T0 + REFRESH_TTL + timedelta(seconds=1))


def test_logout_revokes_family(store):
    user = store.create_anonymous_user()
    t1 = store.issue_refresh(user, now=T0)
    _, t2 = store.rotate(t1, now=T0)
    store.revoke(t2)
    with pytest.raises(InvalidRefreshToken):
        store.rotate(t2, now=T0)
    store.revoke("unknown-token")  # no error


def test_unknown_refresh_token(store):
    with pytest.raises(InvalidRefreshToken):
        store.rotate("never-issued", now=T0)


def test_refresh_tokens_stored_hashed(tmp_path):
    import base64

    from koyala.db.crypto import Crypto

    eng = create_engine(_prepare_db("sqlite", tmp_path))
    store = SqlAuthStore(make_session_factory(eng), Crypto(base64.b64decode(Crypto.generate_key())))
    raw = store.issue_refresh(store.create_anonymous_user())
    with eng.connect() as conn:
        stored = conn.scalars(select(RefreshToken.token_hash)).one()
    assert raw not in stored and len(stored) == 64


# --- API ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(create_app(jwt_secret=SECRET))


def test_api_sign_up_refresh_logout(client):
    r = client.post("/v1/auth/anonymous")
    assert r.status_code == 201
    body = r.json()
    assert body["user_id"].startswith("anon_") and body["token_type"] == "bearer"
    assert body["expires_in"] == 900

    r = client.post("/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 200
    new = r.json()
    assert new["user_id"] == body["user_id"]

    # Old refresh token was consumed; replay is rejected and kills the family.
    replay = client.post("/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert replay.status_code == 401
    after = client.post("/v1/auth/refresh", json={"refresh_token": new["refresh_token"]})
    assert after.status_code == 401


def test_api_logout(client):
    tokens = client.post("/v1/auth/anonymous").json()
    assert (
        client.post("/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}).status_code
        == 204
    )
    r = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401


def test_user_id_comes_from_token_not_client(client):
    a = client.post("/v1/auth/anonymous").json()
    b = client.post("/v1/auth/anonymous").json()
    auth_a = {"Authorization": f"Bearer {a['access_token']}"}
    auth_b = {"Authorization": f"Bearer {b['access_token']}"}
    sid = client.post("/v1/sessions", json={}, headers=auth_a).json()["session_id"]
    # A spoofed legacy header is ignored; B still cannot use A's session.
    spoof = {**auth_b, "X-User-Id": a["user_id"]}
    r = client.post(f"/v1/sessions/{sid}/messages", json={"text": "hi"}, headers=spoof)
    assert r.status_code == 404


def test_public_endpoints_need_no_token(client):
    assert client.get("/healthz").status_code == 200
    assert client.get("/v1/safety/resources").status_code == 200
    assert client.get("/v1/exercises").status_code == 200
