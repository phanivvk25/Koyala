# Risk Detection and Evaluation

## Detectors

| Detector | Code | Status |
|---|---|---|
| **Lexicon** — multilingual phrase patterns (English, Hindi and Telugu in Latin script) | `safety/lexicon.py` | On. Placeholder list needing clinical and linguistic review |
| **LLM risk judge** — Claude classifies each message against a clinical rubric | `safety/judge.py` | **Off by default** (`KOYALA_RISK_JUDGE=anthropic`) |
| **Trained classifier** | `RiskClassifier` slot in `safety/assessor.py` | Not built — needs clinician-labelled data |
| **Floors** — sticky risk after tier 3, PHQ-9 item 9 | `safety/risk_state.py` | On |

The assessor takes the **maximum** of all signals, so a detector can only raise risk, never lower it. If a detector errors, the result is tier 2 (helplines shown).

The judge skips messages the lexicon already rates tier ≥ 3, sends only redacted text plus the last 4 messages, and treats a refusal or bad output as an error (→ tier 2).

## Measuring it

```bash
cd backend
python -m koyala.evals.risk_eval                  # lexicon only, starter set
python -m koyala.evals.risk_eval --judge          # include the LLM judge (needs API key)
python -m koyala.evals.risk_eval my_set.jsonl     # any labelled set
python -m koyala.evals.risk_eval --enforce-gates  # exit 1 unless release gates pass
```

### Release gates (AI Model Spec §9.1)

| Metric | Gate |
|---|---|
| High-risk recall (tier ≥ 3 caught at ≥ 3) | ≥ 95% |
| Imminent miss rate (tier 4 rated below 3) | ≤ 1% |
| Recall gap between languages | ≤ 3 points |

### Current result (lexicon only, synthetic starter set)

| Metric | Value |
|---|---|
| High-risk recall | **51.9%** |
| Imminent miss rate | **63.6%** |
| Recall — direct / indirect / coded phrasing | 81% / 10% / 0% |
| False alarms | 0% |

**Every gate fails.** The starter set (63 messages) was written by engineering, not clinicians, so it shows the shape of the gap rather than a clinical measure. The judge has not yet been measured with a real API key.

## Data format

`koyala/evals/data/*.jsonl`, one message per line:

```json
{"id": "s001", "text": "...", "tier": 3, "lang": "hi-Latn", "style": "indirect"}
```

## What's needed

1. A **clinician-labelled golden set**: ≥ 3,000 messages, balanced across tiers and languages, double-labelled (Cohen's κ ≥ 0.7), with a held-out test split.
2. Measure the judge on it; decide whether to enable it in production (cost and latency).
3. Train the classifier and plug it into the `RiskClassifier` slot.
4. Turn on `--enforce-gates` in CI.

Never tune lexicon patterns on the test split — the numbers will look better than real detection.
