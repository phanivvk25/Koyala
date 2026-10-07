"""Scoring for validated instruments: PHQ-9, GAD-7, WHO-5.

Scores are used for measurement-based care and risk floors only; Koyala never
presents them as a diagnosis (AI Model Spec rule R1).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Instrument(StrEnum):
    PHQ9 = "PHQ9"
    GAD7 = "GAD7"
    WHO5 = "WHO5"


@dataclass(frozen=True)
class _Spec:
    items: int
    item_max: int
    # (upper bound inclusive, band label), ascending.
    bands: tuple[tuple[int, str], ...]


_SPECS: dict[Instrument, _Spec] = {
    Instrument.PHQ9: _Spec(
        items=9,
        item_max=3,
        bands=(
            (4, "minimal"),
            (9, "mild"),
            (14, "moderate"),
            (19, "moderately_severe"),
            (27, "severe"),
        ),
    ),
    Instrument.GAD7: _Spec(
        items=7,
        item_max=3,
        bands=((4, "minimal"), (9, "mild"), (14, "moderate"), (21, "severe")),
    ),
    # WHO-5 bands are on the 0–100 percentage score.
    Instrument.WHO5: _Spec(
        items=5,
        item_max=5,
        bands=((28, "low_wellbeing_screen_for_depression"), (50, "low_wellbeing"), (100, "ok")),
    ),
}

PHQ9_SELF_HARM_ITEM = 8  # zero-based index of item 9


@dataclass(frozen=True)
class AssessmentResult:
    instrument: Instrument
    total: int
    band: str
    # PHQ-9 item 9 ("thoughts that you would be better off dead…") > 0.
    self_harm_flag: bool = False


def score(instrument: Instrument, item_scores: list[int]) -> AssessmentResult:
    spec = _SPECS[instrument]
    if len(item_scores) != spec.items:
        raise ValueError(f"{instrument} requires {spec.items} item scores, got {len(item_scores)}")
    if any(not 0 <= s <= spec.item_max for s in item_scores):
        raise ValueError(f"{instrument} item scores must be between 0 and {spec.item_max}")

    total = sum(item_scores)
    banded = total * 4 if instrument is Instrument.WHO5 else total
    band = next(label for upper, label in spec.bands if banded <= upper)
    self_harm = instrument is Instrument.PHQ9 and item_scores[PHQ9_SELF_HARM_ITEM] > 0
    return AssessmentResult(
        instrument=instrument,
        total=banded,
        band=band,
        self_harm_flag=self_harm,
    )
