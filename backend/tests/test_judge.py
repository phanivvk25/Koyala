import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from koyala.evals import risk_eval
from koyala.main import create_app
from koyala.safety.assessor import RiskAssessor
from koyala.safety.judge import SCHEMA, LLMRiskJudge, RiskJudgeError
from koyala.safety.models import RiskCategory, RiskTier
from koyala.safety.risk_state import InMemoryRiskStateStore
from tests.conftest import sign_up

_REQ = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def _resp(tier=0, categories=(), stop_reason="end_turn", text=None):
    body = text if text is not None else json.dumps({"tier": tier, "categories": list(categories)})
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=body),
        ],
    )


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result(kwargs) if callable(self.result) else self.result


def _judge(result):
    client = FakeClient(result)
    return LLMRiskJudge(client=client, model="claude-opus-5-5"), client


def test_parses_tier_and_categories():
    judge, client = _judge(_resp(4, ["SUI", "MED"]))
    sig = judge.classify("I just swallowed a whole bottle of tablets", [])
    assert sig.tier == RiskTier.IMMINENT
    assert sig.categories == {RiskCategory.SUICIDE, RiskCategory.MEDICAL_EMERGENCY}
    kw = client.calls[0]
    assert kw["output_config"]["format"] == {"type": "json_schema", "schema": SCHEMA}
    assert kw["output_config"]["effort"] == "low"
    assert kw["fallbacks"] == "default"


def test_sends_redacted_text_and_recent_context():
    judge, client = _judge(_resp(0))
    context = [f"old {i}" for i in range(10)] + ["call me on 9876543210"]
    judge.classify("mail me at a@b.com", context)
    content = client.calls[0]["messages"][0]["content"]
    assert "a@b.com" not in content and "[EMAIL]" in content
    assert "9876543210" not in content and "[PHONE]" in content
    assert "old 0" not in content and "old 9" in content  # last 4 context messages only


def test_skips_call_when_lexicon_already_high():
    judge, client = _judge(_resp(0))
    assert judge.classify("I want to kill myself", []).tier == RiskTier.NONE
    assert client.calls == []


@pytest.mark.parametrize(
    "result",
    [
        anthropic.APIConnectionError(request=_REQ),
        anthropic.APITimeoutError(request=_REQ),
        anthropic.RateLimitError("slow", response=httpx2.Response(429, request=_REQ), body=None),
        _resp(stop_reason="refusal"),
        _resp(text="not json"),
        _resp(text=json.dumps({"tier": 9, "categories": []})),
        _resp(text=json.dumps({"tier": 1, "categories": ["NOPE"]})),
    ],
)
def test_failures_raise(result):
    judge, _ = _judge(result)
    with pytest.raises(RiskJudgeError):
        judge.classify("hello", [])


def test_assessor_with_judge_is_raise_only():
    # Judge says 0 but the lexicon says MODERATE: MODERATE wins.
    judge, _ = _judge(_resp(0))
    a = RiskAssessor(InMemoryRiskStateStore(), judge).assess("u", "I wish I was dead")
    assert a.tier == RiskTier.MODERATE


def test_assessor_judge_catches_indirect_risk():
    judge, _ = _judge(_resp(3, ["SUI"]))
    a = RiskAssessor(InMemoryRiskStateStore(), judge).assess("u", "I've been saving up my pills")
    assert a.tier == RiskTier.HIGH and RiskCategory.SUICIDE in a.categories


def test_assessor_judge_failure_fails_safe():
    judge, _ = _judge(anthropic.APIConnectionError(request=_REQ))
    a = RiskAssessor(InMemoryRiskStateStore(), judge).assess("u", "had a fine day")
    assert a.degraded and a.tier == RiskTier.MODERATE


def test_api_crisis_from_judge_never_calls_llm():
    judge, _ = _judge(_resp(4, ["SUI"]))
    calls = []

    class SpyLLM:
        def generate(self, system, messages):
            calls.append(system)
            return "ok"

    client = TestClient(create_app(llm=SpyLLM(), classifier=judge, jwt_secret="s" * 48))
    client.headers.update(sign_up(client))
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    out = client.post(
        f"/v1/sessions/{sid}/messages", json={"text": "the rope is ready, tonight is the night"}
    ).json()
    assert out["type"] == "crisis" and out["risk_tier"] == 4
    assert calls == []


def test_eval_harness_runs_with_judge():
    # A judge that returns each example's gold tier shows the harness wiring works.
    gold = {e.text: int(e.tier) for e in risk_eval.load(risk_eval.DEFAULT_SET)}

    def oracle(kwargs):
        latest = kwargs["messages"][0]["content"].split("Latest message:\n", 1)[1]
        return _resp(gold.get(latest, 0))

    judge, _ = _judge(oracle)
    report = risk_eval.evaluate(classifier=judge)
    assert report.high_recall == 1.0


def test_unknown_judge_env_rejected(monkeypatch):
    monkeypatch.setenv("KOYALA_RISK_JUDGE", "nope")
    with pytest.raises(ValueError):
        create_app(jwt_secret="s" * 48)
