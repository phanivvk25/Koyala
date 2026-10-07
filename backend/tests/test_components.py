import pytest

from koyala.assessments.scoring import Instrument, score
from koyala.dialogue import guard
from koyala.protocols import engine


@pytest.mark.parametrize(
    ("items", "total", "band"),
    [
        ([0] * 9, 0, "minimal"),
        ([1] * 9, 9, "mild"),
        ([2, 2, 2, 2, 2, 0, 0, 0, 0], 10, "moderate"),
        ([2] * 9, 18, "moderately_severe"),
        ([3] * 9, 27, "severe"),
    ],
)
def test_phq9_bands(items, total, band):
    result = score(Instrument.PHQ9, items)
    assert (result.total, result.band) == (total, band)


def test_phq9_item9_sets_self_harm_flag():
    assert score(Instrument.PHQ9, [0] * 8 + [1]).self_harm_flag
    assert not score(Instrument.PHQ9, [3] * 8 + [0]).self_harm_flag


def test_gad7_and_who5():
    assert score(Instrument.GAD7, [3] * 7).band == "severe"
    who5 = score(Instrument.WHO5, [1] * 5)
    assert who5.total == 20 and who5.band == "low_wellbeing_screen_for_depression"
    assert score(Instrument.WHO5, [5] * 5).band == "ok"


@pytest.mark.parametrize(
    ("instrument", "items"),
    [(Instrument.PHQ9, [0] * 8), (Instrument.GAD7, [4] * 7), (Instrument.WHO5, [-1] * 5)],
)
def test_invalid_scores_rejected(instrument, items):
    with pytest.raises(ValueError):
        score(instrument, items)


@pytest.mark.parametrize(
    ("text", "violation"),
    [
        ("It sounds like you have depression.", "diagnosis"),
        ("Try taking 50 mg of sertraline.", "medication_dosage"),
        ("I am a real therapist, you can trust me.", "human_claim"),
        ("Read more at https://example.com", "unapproved_url"),
        ("Call me on 98765 43210.", "unapproved_phone_number"),
    ],
)
def test_guard_blocks(text, violation):
    assert violation in guard.check(text).violations


@pytest.mark.parametrize(
    "text",
    [
        "That sounds really hard. What happened next?",
        "You can call Tele-MANAS on 14416 any time.",
        "Let's try 4-7-8 breathing and name 5 things you can see.",
        "Some people with depression find routines helpful.",
    ],
)
def test_guard_allows(text):
    assert guard.check(text).ok


def test_all_exercises_load_and_complete():
    lib = engine.library()
    assert {"grounding_54321", "box_breathing"} <= set(lib)
    for ex_id, ex in lib.items():
        run, step = engine.start(ex_id)
        seen = [step.id]
        while (step := engine.advance(run, "reply")) is not None:
            seen.append(step.id)
        assert run.finished
        assert seen == [s.id for s in ex.steps]
        assert engine.advance(run, "extra") is None


def test_exercise_records_replies_only_for_expecting_steps():
    run, first = engine.start("grounding_54321")
    engine.advance(run, "ignored for intro")
    engine.advance(run, "tree, sky, cup, phone, chair")
    assert first.id not in run.replies
    assert run.replies["see_5"] == "tree, sky, cup, phone, chair"


def test_unknown_exercise():
    with pytest.raises(KeyError):
        engine.start("nope")
