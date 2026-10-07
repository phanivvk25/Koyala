from datetime import UTC, datetime, timedelta

import pytest

from koyala.safety import crisis, lexicon
from koyala.safety.assessor import RiskAssessor
from koyala.safety.models import RiskCategory, RiskSignal, RiskTier
from koyala.safety.risk_state import RiskStateStore


@pytest.mark.parametrize(
    ("text", "tier"),
    [
        ("Work was really stressful today", RiskTier.NONE),
        ("I feel hopeless about everything", RiskTier.LOW),
        ("Sometimes I wish I could just disappear", RiskTier.MODERATE),
        ("I don't want to be alive anymore", RiskTier.MODERATE),
        ("I want to kill myself", RiskTier.HIGH),
        ("I've been thinking about suicide", RiskTier.HIGH),
        ("I keep cutting myself", RiskTier.HIGH),
        ("I've taken all the pills", RiskTier.IMMINENT),
        ("I'm going to end my life tonight", RiskTier.IMMINENT),
        ("mujhe marna chahta hoon", RiskTier.HIGH),
        ("KILL   MYSELF", RiskTier.HIGH),
        ("I don’t want to live", RiskTier.MODERATE),
    ],
)
def test_lexicon_tiers(text, tier):
    assert lexicon.scan(text).tier == tier


def test_lexicon_reports_categories():
    signal = lexicon.scan("my husband hits me")
    assert RiskCategory.ABUSE in signal.categories


class _BrokenClassifier:
    def classify(self, text, context):
        raise RuntimeError("model server down")


class _FixedClassifier:
    def __init__(self, tier):
        self.tier = tier

    def classify(self, text, context):
        return RiskSignal(source="classifier", tier=self.tier)


def test_classifier_failure_fails_safe_to_moderate():
    assessor = RiskAssessor(RiskStateStore(), _BrokenClassifier())
    result = assessor.assess("u1", "had a fine day")
    assert result.degraded
    assert result.tier == RiskTier.MODERATE


def test_classifier_can_raise_but_lexicon_floor_holds():
    assessor = RiskAssessor(RiskStateStore(), _FixedClassifier(RiskTier.NONE))
    assert assessor.assess("u1", "I want to kill myself").tier == RiskTier.HIGH
    assessor = RiskAssessor(RiskStateStore(), _FixedClassifier(RiskTier.HIGH))
    assert assessor.assess("u2", "fine").tier == RiskTier.HIGH


def test_high_risk_is_sticky_for_72_hours():
    states = RiskStateStore()
    assessor = RiskAssessor(states)
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    assert assessor.assess("u1", "I want to kill myself", now=t0).tier == RiskTier.HIGH
    later = assessor.assess("u1", "ok", now=t0 + timedelta(hours=10))
    assert later.tier == RiskTier.MODERATE
    much_later = assessor.assess("u1", "ok", now=t0 + timedelta(hours=73))
    assert much_later.tier == RiskTier.NONE


def test_sticky_floor_does_not_leak_between_users():
    assessor = RiskAssessor(RiskStateStore())
    assessor.assess("u1", "I want to kill myself")
    assert assessor.assess("u2", "ok").tier == RiskTier.NONE


def test_follow_up_is_scheduled_after_moderate():
    states = RiskStateStore()
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    RiskAssessor(states).assess("u1", "I wish I was dead", now=t0)
    assert states.get("u1").follow_up_due == t0 + timedelta(hours=24)


def test_assessment_floor_expires():
    states = RiskStateStore()
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    states.set_assessment_floor("u1", RiskTier.MODERATE, now=t0)
    assessor = RiskAssessor(states)
    assert assessor.assess("u1", "ok", now=t0 + timedelta(days=1)).tier == RiskTier.MODERATE
    assert assessor.assess("u1", "ok", now=t0 + timedelta(days=15)).tier == RiskTier.NONE


def test_crisis_templates_select_by_tier_and_category():
    assessor = RiskAssessor(RiskStateStore())
    imminent = crisis.crisis_response(assessor.assess("a", "I've taken all the pills"))
    assert imminent.template_id.startswith("crisis_t4")
    assert any(a.number == "112" for a in imminent.actions)

    abuse = crisis.crisis_response(assessor.assess("b", "my father beats me"))
    assert abuse.template_id.startswith("crisis_t3_abuse")

    high = crisis.crisis_response(assessor.assess("c", "I want to kill myself"))
    assert high.template_id.startswith("crisis_t3_v")
    assert {a.kind for a in high.actions} >= {"call", "handoff", "safety_plan"}
