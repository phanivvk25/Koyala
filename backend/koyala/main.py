"""Application factory. Run locally with: uvicorn koyala.main:app --reload

KOYALA_LLM_PROVIDER selects the model backend: "stub" (default, offline) or
"anthropic" (needs Anthropic credentials, e.g. ANTHROPIC_API_KEY).
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from koyala.api.routes import router
from koyala.dialogue.llm import LLMProvider, StubProvider
from koyala.dialogue.orchestrator import Orchestrator
from koyala.safety.assessor import RiskAssessor, RiskClassifier
from koyala.safety.risk_state import RiskStateStore
from koyala.store import SessionStore


def _default_llm() -> LLMProvider:
    provider = os.environ.get("KOYALA_LLM_PROVIDER", "stub")
    if provider == "anthropic":
        from koyala.dialogue.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if provider == "stub":
        return StubProvider()
    raise ValueError(f"unknown KOYALA_LLM_PROVIDER: {provider}")


def create_app(
    llm: LLMProvider | None = None,
    classifier: RiskClassifier | None = None,
) -> FastAPI:
    app = FastAPI(title="Koyala API", version="0.1.0")
    risk_states = RiskStateStore()
    app.state.risk_states = risk_states
    app.state.sessions = SessionStore()
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
