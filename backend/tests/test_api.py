import pytest
from fastapi.testclient import TestClient

from koyala.dialogue.llm import LLMUnavailable
from koyala.main import create_app

USER = {"X-User-Id": "user-1"}


class SpyLLM:
    def __init__(self, replies=None, error=None):
        self.replies = list(replies or ["I'm listening. What's on your mind?"])
        self.error = error
        self.calls = []

    def generate(self, system, messages):
        self.calls.append(system)
        if self.error:
            raise self.error
        return self.replies[min(len(self.calls), len(self.replies)) - 1]


def _client(llm=None):
    return TestClient(create_app(llm=llm or SpyLLM()))


def _session(client, headers=USER):
    return client.post("/v1/sessions", json={}, headers=headers).json()["session_id"]


def _say(client, sid, text, headers=USER):
    r = client.post(f"/v1/sessions/{sid}/messages", json={"text": text}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_normal_turn_uses_llm():
    llm = SpyLLM()
    client = _client(llm)
    out = _say(client, _session(client), "Work has been stressful")
    assert out["type"] == "message"
    assert out["risk_tier"] == 0
    assert len(llm.calls) == 1


def test_crisis_turn_never_calls_llm():
    llm = SpyLLM()
    client = _client(llm)
    out = _say(client, _session(client), "I want to kill myself")
    assert out["type"] == "crisis"
    assert out["risk_tier"] == 3
    assert out["template_id"].startswith("crisis_t3")
    assert any(a["kind"] == "handoff" for a in out["actions"])
    assert llm.calls == []


def test_moderate_risk_explores_and_shows_resources():
    llm = SpyLLM()
    client = _client(llm)
    out = _say(client, _session(client), "I wish I could just disappear")
    assert out["risk_tier"] == 2
    assert "ACTION: RISK_EXPLORE" in llm.calls[0]
    assert any(a.get("number") == "14416" for a in out["actions"])


def test_llm_outage_returns_fallback():
    client = _client(SpyLLM(error=LLMUnavailable()))
    out = _say(client, _session(client), "hello")
    assert out["type"] == "fallback"
    assert any(a["kind"] == "call" for a in out["actions"])


def test_guard_regenerates_then_accepts():
    llm = SpyLLM(replies=["You have depression.", "That sounds heavy. Tell me more?"])
    client = _client(llm)
    out = _say(client, _session(client), "I feel low")
    assert out["text"] == "That sounds heavy. Tell me more?"
    assert len(llm.calls) == 2


def test_guard_falls_back_after_two_failures():
    llm = SpyLLM(replies=["You have depression."])
    client = _client(llm)
    out = _say(client, _session(client), "I feel low")
    assert out["type"] == "fallback"
    assert len(llm.calls) == 2


def test_exercise_flow_and_crisis_interrupts_it():
    client = _client()
    sid = _session(client)
    offer = _say(client, sid, "can you help me calm down")
    assert any(a["ref"] == "grounding_54321" for a in offer["actions"])

    r = client.post(
        f"/v1/sessions/{sid}/exercise", json={"exercise_id": "grounding_54321"}, headers=USER
    )
    assert r.json()["step_id"] == "intro"
    assert _say(client, sid, "ready")["step_id"] == "see_5"

    out = _say(client, sid, "I want to kill myself")
    assert out["type"] == "crisis"
    # Exercise was cancelled; next turn is not an exercise step.
    assert _say(client, sid, "ok")["type"] != "exercise_step"


def test_exercise_can_be_stopped():
    client = _client()
    sid = _session(client)
    client.post(f"/v1/sessions/{sid}/exercise", json={"exercise_id": "box_breathing"}, headers=USER)
    out = _say(client, sid, "stop")
    assert out["type"] == "message"
    assert "stop" in out["text"].lower()


def test_sessions_are_private_to_their_user():
    client = _client()
    sid = _session(client)
    r = client.post(
        f"/v1/sessions/{sid}/messages", json={"text": "hi"}, headers={"X-User-Id": "intruder"}
    )
    assert r.status_code == 404


def test_missing_user_header_rejected():
    client = _client()
    assert client.post("/v1/sessions", json={}).status_code == 422


def test_phq9_item9_triggers_follow_up_and_risk_floor():
    llm = SpyLLM()
    client = _client(llm)
    r = client.post(
        "/v1/assessments", json={"instrument": "PHQ9", "item_scores": [1] * 9}, headers=USER
    )
    body = r.json()
    assert body["self_harm_flag"] and body["follow_up"]["risk_tier"] == 2

    out = _say(client, _session(client), "I'm okay I guess")
    assert out["risk_tier"] == 2
    assert "ACTION: RISK_EXPLORE" in llm.calls[0]


@pytest.mark.parametrize("items", [[0] * 3, [9] * 9])
def test_invalid_assessment_rejected(items):
    client = _client()
    r = client.post(
        "/v1/assessments", json={"instrument": "PHQ9", "item_scores": items}, headers=USER
    )
    assert r.status_code == 422


def test_public_endpoints():
    client = _client()
    assert client.get("/healthz").json() == {"status": "ok"}
    numbers = {r["number"] for r in client.get("/v1/safety/resources").json()}
    assert {"112", "14416"} <= numbers
    assert len(client.get("/v1/exercises").json()) >= 2
