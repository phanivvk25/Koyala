import json

import pytest

from koyala.evals import risk_eval
from koyala.evals.risk_eval import DEFAULT_SET, Example, Prediction, load, score
from koyala.safety.models import RiskSignal, RiskTier

T = RiskTier


def _p(gold, pred, lang="en", style="direct", i=0):
    return Prediction(Example(f"x{i}", "t", T(gold), lang, style), T(pred))


def test_metrics_on_known_predictions():
    preds = [
        _p(4, 4, i=1),
        _p(4, 1, i=2),  # imminent miss
        _p(3, 3, i=3),
        _p(3, 2, i=4),  # under-triaged high risk
        _p(2, 2, i=5),
        _p(0, 0, i=6),
        _p(0, 2, i=7),  # false alarm
    ]
    r = score(preds)
    assert r.high_recall == pytest.approx(2 / 4)
    assert r.imminent_fnr == pytest.approx(1 / 2)
    assert r.any_risk_recall == pytest.approx(4 / 5)
    assert r.false_alarm_rate == pytest.approx(1 / 2)
    assert r.confusion["4"] == {"4": 1, "1": 1}
    assert [m["id"] for m in r.misses] == ["x2", "x4"]
    assert not r.passed


def test_gates_pass_on_perfect_predictions():
    preds = [
        _p(t, t, lang=lang, i=i)
        for i, (t, lang) in enumerate([(4, "en"), (3, "hi-Latn"), (2, "en"), (0, "en")])
    ]
    r = score(preds)
    assert r.passed
    assert all(r.gates.values())


def test_language_gap_gate():
    preds = [_p(3, 3, lang="en", i=1), _p(3, 0, lang="hi-Latn", i=2)]
    assert score(preds).gates["language_gap<=0.03"] is False


def test_starter_set_is_well_formed():
    examples = load(DEFAULT_SET)
    assert len({e.id for e in examples}) == len(examples)
    assert {e.tier for e in examples} == set(RiskTier)
    assert {"en", "hi-Latn", "te-Latn"} <= {e.lang for e in examples}


def test_invalid_example_rejected(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({"id": "a", "text": "x", "tier": 9}) + "\n")
    with pytest.raises(ValueError, match="bad.jsonl:1"):
        load(bad)


class _AlwaysHigh:
    def classify(self, text, context):
        return RiskSignal(source="classifier", tier=RiskTier.HIGH)


def test_classifier_is_evaluated_with_lexicon():
    r = risk_eval.evaluate(DEFAULT_SET, classifier=_AlwaysHigh())
    assert r.high_recall == 1.0
    assert r.false_alarm_rate == 1.0


# --- No-regression floor -----------------------------------------------------------
# Baseline of the current lexicon on the synthetic starter set. It is far below the
# release gates (see koyala/evals/data/README.md); this only stops it getting worse.
# Raise these numbers when detection improves; never lower them.
BASELINE_HIGH_RECALL = 0.51
BASELINE_ANY_RISK_RECALL = 0.48
MAX_FALSE_ALARM_RATE = 0.0


def test_lexicon_does_not_regress():
    r = risk_eval.evaluate()
    assert r.high_recall >= BASELINE_HIGH_RECALL
    assert r.any_risk_recall >= BASELINE_ANY_RISK_RECALL
    assert r.false_alarm_rate <= MAX_FALSE_ALARM_RATE


def test_cli_runs(capsys):
    assert risk_eval.main([]) == 0
    assert "High-risk recall" in capsys.readouterr().out
    assert risk_eval.main(["--enforce-gates"]) == 1
