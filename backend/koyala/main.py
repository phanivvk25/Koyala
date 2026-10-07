"""Application factory. Run locally with: uvicorn koyala.main:app --reload"""

from __future__ import annotations

from fastapi import FastAPI

from koyala.api.routes import router
from koyala.dialogue.llm import LLMProvider, StubProvider
from koyala.dialogue.orchestrator import Orchestrator
from koyala.safety.assessor import RiskAssessor, RiskClassifier
from koyala.safety.risk_state import RiskStateStore
from koyala.store import SessionStore


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
        llm=llm or StubProvider(),
    )
    app.include_router(router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
