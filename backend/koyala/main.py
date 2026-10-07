"""Application factory. Run locally with: uvicorn koyala.main:app --reload

KOYALA_LLM_PROVIDER selects the model backend: "stub" (default, offline) or
"anthropic" (needs Anthropic credentials, e.g. ANTHROPIC_API_KEY).

KOYALA_DATABASE_URL (e.g. postgresql+psycopg://user:pass@host/koyala) switches
storage from in-memory to the database; KOYALA_MASTER_KEY is then required.
Run migrations first: python -m koyala.db.migrate
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from koyala.api.routes import router
from koyala.dialogue.llm import LLMProvider, StubProvider
from koyala.dialogue.orchestrator import Orchestrator
from koyala.safety.assessor import RiskAssessor, RiskClassifier
from koyala.safety.risk_state import InMemoryRiskStateStore, RiskStateStore
from koyala.store import InMemorySessionStore, SessionStore


def _default_llm() -> LLMProvider:
    provider = os.environ.get("KOYALA_LLM_PROVIDER", "stub")
    if provider == "anthropic":
        from koyala.dialogue.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if provider == "stub":
        return StubProvider()
    raise ValueError(f"unknown KOYALA_LLM_PROVIDER: {provider}")


def _default_stores() -> tuple[SessionStore, RiskStateStore]:
    url = os.environ.get("KOYALA_DATABASE_URL")
    if not url:
        return InMemorySessionStore(), InMemoryRiskStateStore()
    from sqlalchemy import create_engine

    from koyala.db.crypto import Crypto
    from koyala.db.stores import SqlRiskStateStore, SqlSessionStore, make_session_factory

    crypto = Crypto.from_env()
    factory = make_session_factory(create_engine(url, pool_pre_ping=True))
    return SqlSessionStore(factory, crypto), SqlRiskStateStore(factory, crypto)


def create_app(
    llm: LLMProvider | None = None,
    classifier: RiskClassifier | None = None,
    stores: tuple[SessionStore, RiskStateStore] | None = None,
) -> FastAPI:
    app = FastAPI(title="Koyala API", version="0.1.0")
    sessions, risk_states = stores or _default_stores()
    app.state.risk_states = risk_states
    app.state.sessions = sessions
    app.state.orchestrator = Orchestrator(
        assessor=RiskAssessor(risk_states, classifier),
        llm=llm or _default_llm(),
    )
    app.include_router(router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
