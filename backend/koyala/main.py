"""Application factory. Run locally with: uvicorn koyala.main:app --reload

KOYALA_LLM_PROVIDER selects the model backend: "stub" (default, offline) or
"anthropic" (needs Anthropic credentials, e.g. ANTHROPIC_API_KEY).

KOYALA_DATABASE_URL (e.g. postgresql+psycopg://user:pass@host/koyala) switches
storage from in-memory to the database; KOYALA_MASTER_KEY and
KOYALA_JWT_SECRET are then required. Run migrations first:
python -m koyala.db.migrate
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass

from fastapi import FastAPI

from koyala.api.auth_routes import router as auth_router
from koyala.api.checkin_routes import router as checkin_router
from koyala.api.escalation_routes import router as escalation_router
from koyala.api.privacy_routes import router as privacy_router
from koyala.api.routes import router
from koyala.api.tracking_routes import router as tracking_router
from koyala.auth.refresh import AuthStore, InMemoryAuthStore
from koyala.auth.service import AuthService
from koyala.auth.tokens import TokenService
from koyala.dialogue.llm import LLMProvider, StubProvider
from koyala.dialogue.orchestrator import Orchestrator
from koyala.escalation import (
    CrisisPartner,
    EscalationService,
    EscalationStore,
    InMemoryEscalationStore,
    LogPager,
    Pager,
    StubPartner,
)
from koyala.privacy import InMemoryPrivacyStore, PrivacyStore
from koyala.safety.assessor import RiskAssessor, RiskClassifier
from koyala.safety.risk_state import InMemoryRiskStateStore, RiskStateStore
from koyala.store import InMemorySessionStore, SessionStore
from koyala.tracking import InMemoryTrackingStore, TrackingStore

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Stores:
    sessions: SessionStore
    risk_states: RiskStateStore
    auth: AuthStore
    tracking: TrackingStore
    escalations: EscalationStore
    privacy: PrivacyStore
    persistent: bool = False


def _default_llm() -> LLMProvider:
    provider = os.environ.get("KOYALA_LLM_PROVIDER", "stub")
    if provider == "anthropic":
        from koyala.dialogue.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if provider == "stub":
        return StubProvider()
    raise ValueError(f"unknown KOYALA_LLM_PROVIDER: {provider}")


def _default_stores() -> Stores:
    url = os.environ.get("KOYALA_DATABASE_URL")
    if not url:
        sessions, risk, auth = InMemorySessionStore(), InMemoryRiskStateStore(), InMemoryAuthStore()
        tracking, escalations = InMemoryTrackingStore(), InMemoryEscalationStore()
        privacy = InMemoryPrivacyStore(sessions, risk, auth, tracking, escalations)
        return Stores(sessions, risk, auth, tracking, escalations, privacy)
    from sqlalchemy import create_engine

    from koyala.db.crypto import Crypto
    from koyala.db.stores import (
        SqlAuthStore,
        SqlEscalationStore,
        SqlPrivacyStore,
        SqlRiskStateStore,
        SqlSessionStore,
        SqlTrackingStore,
        make_session_factory,
    )

    crypto = Crypto.from_env()
    factory = make_session_factory(create_engine(url, pool_pre_ping=True))
    tracking = SqlTrackingStore(factory, crypto)
    escalations = SqlEscalationStore(factory, crypto)
    return Stores(
        SqlSessionStore(factory, crypto),
        SqlRiskStateStore(factory, crypto),
        SqlAuthStore(factory, crypto),
        tracking,
        escalations,
        SqlPrivacyStore(factory, crypto, tracking, escalations),
        persistent=True,
    )


def _jwt_secret(persistent: bool) -> str:
    secret = os.environ.get("KOYALA_JWT_SECRET")
    if secret:
        return secret
    if persistent:
        raise RuntimeError("KOYALA_JWT_SECRET is required when a database is configured")
    # In-memory dev mode: tokens die with the process anyway.
    log.warning("KOYALA_JWT_SECRET not set; using a random development secret")
    return secrets.token_urlsafe(48)


def create_app(
    llm: LLMProvider | None = None,
    classifier: RiskClassifier | None = None,
    stores: Stores | None = None,
    jwt_secret: str | None = None,
    partner: CrisisPartner | None = None,
    pager: Pager | None = None,
) -> FastAPI:
    app = FastAPI(title="Koyala API", version="0.1.0")
    stores = stores or _default_stores()
    tokens = TokenService(jwt_secret or _jwt_secret(stores.persistent))
    app.state.auth = AuthService(tokens, stores.auth)
    app.state.risk_states = stores.risk_states
    app.state.sessions = stores.sessions
    app.state.tracking = stores.tracking
    app.state.privacy = stores.privacy
    app.state.escalations = EscalationService(
        stores.escalations, partner or StubPartner(), pager or LogPager()
    )
    app.state.assessor = RiskAssessor(stores.risk_states, classifier)
    app.state.orchestrator = Orchestrator(
        assessor=app.state.assessor,
        llm=llm or _default_llm(),
    )
    app.include_router(auth_router)
    app.include_router(router)
    app.include_router(tracking_router)
    app.include_router(escalation_router)
    app.include_router(privacy_router)
    app.include_router(checkin_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
