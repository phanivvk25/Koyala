# Risk evaluation data

`risk_starter.jsonl` is a **synthetic starter set written by engineering, not
clinicians**. It exists so the evaluation harness has something to run on and
to illustrate the kinds of phrasing the risk layer must handle (direct,
indirect, coded, Hindi/Telugu in Latin script). It is **not** a valid
measure of clinical performance and must not be cited as one.

Replace it with a clinician-labelled golden set (AI Model Spec §7.3, §9.1):
≥ 3,000 messages, balanced across tiers 0–4 and languages, each double-labelled
by licensed clinicians with inter-rater agreement (Cohen's κ ≥ 0.7) and
adjudication. Keep the same JSONL fields:

| field | meaning |
|---|---|
| `id` | stable id |
| `text` | the user message |
| `tier` | gold risk tier 0–4 |
| `lang` | `en`, `hi-Latn`, `te-Latn`, `hi`, `te`, `mixed`, ... |
| `style` | `direct`, `indirect` or `coded` |

Hold out a test split that is never used for training or for tuning lexicon
patterns, otherwise the reported numbers will be optimistic.
