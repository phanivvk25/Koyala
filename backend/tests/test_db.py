"""Database layer tests.

Run against SQLite always, and against PostgreSQL when KOYALA_TEST_DATABASE_URL
is set (CI sets it). The PostgreSQL database is wiped for each test.
"""

import base64
import os
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from cryptography.exceptions import InvalidTag
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text

from koyala.db.crypto import Crypto
from koyala.db.migrate import alembic_config, upgrade
from koyala.db.models import Base, ChatSession, Message, RiskEvent
from koyala.db.stores import (
    HISTORY_WINDOW,
    SqlAuthStore,
    SqlRiskStateStore,
    SqlSessionStore,
    make_session_factory,
)
from koyala.dialogue.llm import ChatMessage
from koyala.main import Stores, create_app
from koyala.protocols import engine as exercises
from koyala.safety.models import RiskCategory, RiskTier
from koyala.safety.risk_state import InMemoryRiskStateStore

PG_URL = os.environ.get("KOYALA_TEST_DATABASE_URL")
BACKENDS = ["sqlite"] + (["postgres"] if PG_URL else [])
T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _prepare_db(backend, tmp_path):
    if backend == "sqlite":
        url = f"sqlite:///{tmp_path / 'koyala.db'}"
    else:
        url = PG_URL
        eng = create_engine(url)
        with eng.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        eng.dispose()
    upgrade(url)
    return url


@pytest.fixture(params=BACKENDS)
def db_url(request, tmp_path):
    return _prepare_db(request.param, tmp_path)


@pytest.fixture
def crypto():
    return Crypto(base64.b64decode(Crypto.generate_key()))


@pytest.fixture
def db(db_url, crypto):
    eng = create_engine(db_url)
    factory = make_session_factory(eng)
    yield eng, SqlSessionStore(factory, crypto), SqlRiskStateStore(factory, crypto)
    eng.dispose()


# --- migrations -------------------------------------------------------------


def test_migrations_match_models(db_url):
    eng = create_engine(db_url)
    with eng.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    eng.dispose()
    assert diff == []


def test_migrations_downgrade_and_reapply(db_url):
    command.downgrade(alembic_config(db_url), "base")
    upgrade(db_url)


# --- sessions ---------------------------------------------------------------


def test_session_round_trip(db):
    _, sessions, _ = db
    s = sessions.create("u1", "te")
    s.history += [ChatMessage("user", "hello"), ChatMessage("assistant", "hi there")]
    s.exercise_run, _ = exercises.start("grounding_54321")
    exercises.advance(s.exercise_run, "ready")
    exercises.advance(s.exercise_run, "tree, sky")
    sessions.save(s)
    sessions.save(s)  # idempotent: nothing new to write

    loaded = sessions.get(s.id)
    assert loaded.user_id == "u1" and loaded.language == "te"
    assert loaded.history == s.history
    assert loaded.exercise_run == s.exercise_run
    assert loaded.persisted == 2

    loaded.exercise_run = None
    loaded.history.append(ChatMessage("user", "thanks"))
    sessions.save(loaded)
    again = sessions.get(s.id)
    assert [m.content for m in again.history] == ["hello", "hi there", "thanks"]
    assert again.exercise_run is None


def test_session_history_window_and_sequence(db):
    eng, sessions, _ = db
    s = sessions.create("u1")
    s.history = [ChatMessage("user", f"m{i}") for i in range(HISTORY_WINDOW + 5)]
    sessions.save(s)

    loaded = sessions.get(s.id)
    assert len(loaded.history) == HISTORY_WINDOW
    assert loaded.history[0].content == "m5"
    loaded.history.append(ChatMessage("assistant", "latest"))
    sessions.save(loaded)

    with eng.connect() as conn:
        seqs = conn.scalars(
            select(Message.seq).where(Message.session_id == s.id).order_by(Message.seq)
        ).all()
    assert seqs == list(range(HISTORY_WINDOW + 6))


def test_unknown_session(db):
    _, sessions, _ = db
    assert sessions.get("does-not-exist") is None


def test_content_is_encrypted_at_rest(db):
    eng, sessions, _ = db
    s = sessions.create("u1")
    s.history.append(ChatMessage("user", "I feel very anxious about exams"))
    s.exercise_run, _ = exercises.start("grounding_54321")
    exercises.advance(s.exercise_run, "x")
    exercises.advance(s.exercise_run, "my secret reply")
    sessions.save(s)
    with eng.connect() as conn:
        blob = conn.scalars(select(Message.content_enc)).one()
        state = conn.scalars(select(ChatSession.exercise_state_enc)).one()
    assert b"anxious" not in blob
    assert b"secret" not in state


# --- encryption -------------------------------------------------------------


def test_ciphertext_bound_to_user(crypto):
    dek = crypto.new_wrapped_dek("alice")
    blob = crypto.encrypt(dek, "alice", "private")
    assert crypto.decrypt(dek, "alice", blob) == "private"
    with pytest.raises(InvalidTag):
        crypto.decrypt(dek, "bob", blob)


def test_wrong_master_key_cannot_decrypt(crypto):
    dek = crypto.new_wrapped_dek("alice")
    blob = crypto.encrypt(dek, "alice", "private")
    other = Crypto(base64.b64decode(Crypto.generate_key()))
    with pytest.raises(InvalidTag):
        other.decrypt(dek, "alice", blob)


def test_master_key_validation(monkeypatch):
    with pytest.raises(ValueError):
        Crypto(b"short")
    monkeypatch.delenv("KOYALA_MASTER_KEY", raising=False)
    with pytest.raises(RuntimeError):
        Crypto.from_env()


# --- risk state (same contract for both stores) -------------------------------


@pytest.fixture(params=["memory", *BACKENDS])
def risk_store(request, tmp_path, crypto):
    if request.param == "memory":
        yield InMemoryRiskStateStore()
        return
    eng = create_engine(_prepare_db(request.param, tmp_path))
    yield SqlRiskStateStore(make_session_factory(eng), crypto)
    eng.dispose()


def test_risk_store_sticky_floor_and_follow_up(risk_store):
    risk_store.record_turn("u1", RiskTier.HIGH, T0)
    state = risk_store.get("u1")
    assert state.peak_tier == RiskTier.HIGH
    assert state.floor(T0 + timedelta(hours=1)) == RiskTier.MODERATE
    assert state.floor(T0 + timedelta(hours=73)) == RiskTier.NONE
    assert state.follow_up_due == T0 + timedelta(hours=12)
    # A later, lower tier does not replace the peak inside the window.
    risk_store.record_turn("u1", RiskTier.MODERATE, T0 + timedelta(hours=2))
    assert risk_store.get("u1").peak_at == T0


def test_risk_store_assessment_floor(risk_store):
    risk_store.set_assessment_floor("u2", RiskTier.MODERATE, T0)
    state = risk_store.get("u2")
    assert state.floor(T0 + timedelta(days=1)) == RiskTier.MODERATE
    assert state.floor(T0 + timedelta(days=15)) == RiskTier.NONE


def test_risk_store_unknown_user_has_no_risk(risk_store):
    assert risk_store.get("nobody").floor(T0) == RiskTier.NONE


def test_risk_events_audit_trail(db):
    eng, _, risk = db
    risk.record_turn("u1", RiskTier.NONE, T0)
    risk.record_turn("u1", RiskTier.LOW, T0)
    risk.record_turn("u1", RiskTier.HIGH, T0, {RiskCategory.SUICIDE})
    with eng.connect() as conn:
        rows = conn.execute(select(RiskEvent.tier, RiskEvent.categories)).all()
    assert rows == [(3, ["SUI"])]


# --- end to end ---------------------------------------------------------------


JWT_SECRET = "test-secret-" + "x" * 40


def _sql_stores(db_url, crypto):
    factory = make_session_factory(create_engine(db_url))
    return Stores(
        SqlSessionStore(factory, crypto),
        SqlRiskStateStore(factory, crypto),
        SqlAuthStore(factory, crypto),
        persistent=True,
    )


def test_state_survives_app_restart(db_url, crypto):
    def app():
        return TestClient(create_app(stores=_sql_stores(db_url, crypto), jwt_secret=JWT_SECRET))

    first = app()
    tokens = first.post("/v1/auth/anonymous").json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    sid = first.post("/v1/sessions", json={}, headers=headers).json()["session_id"]
    out = first.post(
        f"/v1/sessions/{sid}/messages", json={"text": "I want to kill myself"}, headers=headers
    ).json()
    assert out["type"] == "crisis"

    second = app()  # simulates a restart: fresh process state, same database
    out = second.post(f"/v1/sessions/{sid}/messages", json={"text": "ok"}, headers=headers).json()
    assert out["risk_tier"] == 2  # sticky floor persisted
    # Refresh token issued before the restart still works.
    assert (
        second.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code
        == 200
    )
    history = SqlSessionStore(make_session_factory(create_engine(db_url)), crypto).get(sid)
    assert [m.role for m in history.history] == ["user", "assistant", "user", "assistant"]


def test_jwt_secret_required_with_database(db_url, crypto, monkeypatch):
    monkeypatch.delenv("KOYALA_JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        create_app(stores=_sql_stores(db_url, crypto))
