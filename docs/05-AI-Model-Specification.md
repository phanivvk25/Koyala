# Koyala — AI Model Specification

| Field | Value |
|---|---|
| Document | AI Model Spec v0.1 (Draft) |
| Depends on | PRD (03), TDD (04) |
| Related | Safety Protocol (06), Compliance (07) |
| Status | Draft for review |

---

## 1. Purpose

Specifies the AI components of Koyala: their responsibilities, behaviour rules, data, training, guardrails, and evaluation. It is the reference for ML engineers, clinicians reviewing model behaviour, and auditors.

## 2. Design Philosophy

- **Compound system, not a single model.** An LLM generates language; specialised classifiers, rules and a protocol engine decide *what* to do and enforce *safety*.
- **Recall over precision for risk.** Missing a crisis is far worse than an unnecessary check-in.
- **Grounded, not improvised.** Therapeutic content comes from clinician-approved protocols and a curated knowledge base.
- **Human oversight.** Clinicians define, review and audit behaviour.

## 3. Component Inventory

| # | Component | Type | Input | Output | Latency budget |
|---|---|---|---|---|---|
| C1 | Language ID & normaliser | Small classifier + transliteration | Text | lang, script, normalised text | 20 ms |
| C2 | PII detector/redactor | NER + regex | Text | redacted text, entity map | 30 ms |
| C3 | Risk lexicon fast-path | Multilingual lexicon/regex | Normalised text | hit categories | 5 ms |
| C4 | Risk classifier | Fine-tuned multilingual encoder | Message + last 6 turns | P(tier 0–4), categories | 100 ms |
| C5 | LLM risk judge | LLM with rubric prompt | Context (redacted) | tier, rationale | 800 ms (async when C4 tier < 2) |
| C6 | Intent classifier | Encoder | Message + mode | {vent, skill, learn, checkin, smalltalk, out_of_scope, feedback} | 50 ms |
| C7 | Emotion classifier | Multi-label encoder | Message | ~28 emotion labels + intensity | 50 ms |
| C8 | Cognitive distortion tagger | Encoder or LLM | Message | distortion labels (10 types) | 100 ms |
| C9 | Dialogue policy | Rules + contextual bandit (later) | User state | next_action | 10 ms |
| C10 | Protocol engine | Deterministic FSM | Exercise YAML + state | step content | 5 ms |
| C11 | Retriever (RAG) | Embeddings + pgvector | Query | top-k approved passages | 80 ms |
| C12 | Response generator | Frontier LLM (hosted) | System prompt + policy + context | Response | first token < 1.5 s |
| C13 | Output guard | Classifier + LLM check + rules | Draft response | pass / block / rewrite | 200 ms |
| C14 | Memory summariser | LLM (async) | Session transcript | structured memory items | async |
| C15 | Clinical note drafter (Ph3) | LLM | Transcript + scores | SOAP/DAP draft | async |
| C16 | Insight generator | Stats + LLM wording | Mood/assessment series | weekly insight | async |
| C17 | Deterioration predictor (Ph4) | GBM / time-series | Engagement + scores | P(deterioration) → human outreach only | batch |

## 4. Risk Model (C3–C5)

### 4.1 Tier definitions
| Tier | Definition | Examples |
|---|---|---|
| 0 | No risk indicators | "Work was stressful today" |
| 1 | Distress / hopelessness without self-harm reference | "Nothing ever works out for me" |
| 2 | Passive ideation or past self-harm mention, no current plan | "Sometimes I wish I could just disappear" |
| 3 | Active ideation, or plan, or recent self-harm, or harm-to-others intent | "I've been thinking about how I'd do it" |
| 4 | Imminent: intent + means + timeframe, or attempt in progress, or medical emergency | "I've taken the pills" |

### 4.2 Aggregation logic
```
tier = max(
  lexicon_tier (C3, conservative mapping),
  classifier_tier (C4, calibrated thresholds tuned for recall),
  judge_tier (C5, when invoked),
  assessment_floor (e.g., PHQ-9 item 9 ≥ 2 in last 14 days → floor tier 2),
  sticky_floor (risk_state decay: tier 3 → floor 2 for 72 h)
)
```
- C5 invoked synchronously when C4 tier ∈ {1,2,3} with confidence < 0.8, or when C3 and C4 disagree by ≥2 tiers.
- Classifier may **raise** but C5 may only **lower** a tier if C3 had no hit **and** confidence is high **and** tier ≤ 2 (prevents the LLM from talking itself out of a crisis).

### 4.3 Special detection categories
- Harm to others, domestic violence, child abuse/neglect, sexual violence.
- Medical emergency (overdose, poisoning, chest pain, injury).
- Psychosis / mania indicators (out-of-scope → gentle referral).
- Eating disorder red flags; substance use crisis.
- Indirect & coded expressions, emoji sequences, "asking for a friend", song lyrics/quotes, code-mixed and transliterated phrases (e.g., Hindi/Telugu in Latin script).

## 5. Response Generator (C12)

### 5.1 Model choice
- Primary: hosted frontier LLM with strong multilingual/Indic performance, enterprise zero-data-retention terms, and available in-region or with acceptable cross-border terms (see doc 07).
- Fallback: second provider or self-hosted open-weight model for degraded mode.
- Selection is via bake-off on the evaluation suite (§8), per language.

### 5.2 System prompt structure (versioned in prompt registry)
1. **Identity & role**: "You are Koyala, an AI companion for emotional wellbeing. You are not a therapist, doctor or emergency service."
2. **Style**: warm, non-judgemental, concise (≤ 120 words default), one question at a time, reflect before advising, user's language & script, grade 6–8 reading level.
3. **Therapeutic stance**: MI spirit (collaboration, evocation, autonomy), validation, strengths-based.
4. **Current policy action** (from C9): e.g., `REFLECT_AND_ASK_OPEN`, `DELIVER_STEP(grounding.see5)`, `PSYCHOED(topic=panic_cycle)`.
5. **Grounding**: retrieved passages (C11) and exercise step script (C10) — "use only this content for factual claims".
6. **User context**: preferred name/alias, goals, consented memory items, current mood score.
7. **Hard rules** (§5.3).

### 5.3 Behaviour rules — MUST NOT
| ID | Rule |
|---|---|
| R1 | Do not diagnose or label the user with a disorder |
| R2 | Do not recommend, adjust, or comment on dosage of medication; refer to prescriber |
| R3 | Never provide information that could facilitate self-harm, suicide, or harm to others (methods, lethality, means) |
| R4 | Never claim to be human, licensed, or to have feelings/experiences of a person |
| R5 | Do not encourage dependence ("I'm all you need") or discourage professional help or relationships |
| R6 | No romantic, sexual, or flirtatious content; decline role-play that blurs boundaries |
| R7 | Do not validate delusional content; respond with empathy to the feeling, not agreement with the belief |
| R8 | Do not make promises of confidentiality beyond the published policy |
| R9 | Do not give legal, financial or medical advice beyond general signposting |
| R10 | Do not moralise, shame, or use religious framing unless the user has chosen faith-sensitive mode |

### 5.4 Behaviour rules — MUST
| ID | Rule |
|---|---|
| M1 | Acknowledge feelings before offering techniques |
| M2 | Ask permission before starting an exercise |
| M3 | Ask directly about suicide when policy requests risk exploration (clinically recommended practice) |
| M4 | Encourage human support and professional help where appropriate |
| M5 | Respect user autonomy; offer choices |
| M6 | Keep cultural context in mind (family, exams, marriage pressure, stigma) |
| M7 | End sessions with a brief summary and one small next step |

## 6. Output Guardrails (C13)

Applied to every generated response before display:
1. **Safety classifier** on response (harmful instructions, self-harm content, sexual content).
2. **Rule checks**: diagnosis patterns, medication dosage patterns, phone numbers not in approved directory, URLs not allow-listed.
3. **Consistency check**: response aligns with policy action (e.g., not skipping a crisis follow-up).
4. **Tone check** (lightweight classifier): dismissive / preachy / cold → regenerate.
5. **Length & reading-level check**.
6. On failure: regenerate once with stricter instructions → if still failing, serve a safe fallback template and log for review.

## 7. Data Strategy

### 7.1 Data sources
| Source | Use | Conditions |
|---|---|---|
| Clinician-authored synthetic dialogues | SFT, eval | Written by licensed professionals per scenario matrix |
| Public emotional-support datasets (e.g., ESConv, GoEmotions) | Pre-training classifiers, eval | License review; filter quality |
| Risk research datasets (e.g., CLPsych shared tasks) | Risk classifier | Data-use agreements; ethics approval |
| Translated & culturally adapted data | Indic coverage | Professional translation + clinician review; not raw MT |
| Beta-user conversations | Improvement | **Explicit research opt-in only**, de-identified, ethics committee approval |

### 7.2 Scenario matrix (for synthetic data & eval)
Dimensions: condition (stress, anxiety, low mood, grief, sleep, relationship, academic, work, loneliness, trauma-adjacent) × risk tier (0–4) × language/script (EN, HI, TE, code-mixed) × persona (age band, gender, region, urban/rural) × conversation phase (opening, exploring, exercise, closing, return visit).

### 7.3 Annotation
- Annotators: licensed clinicians for risk & therapeutic quality; trained linguists for language.
- Guidelines: risk tier definitions (§4.1), empathy rubric (EPITOME-style: emotional reactions, interpretations, explorations), MI-consistency, rule violations.
- Quality: double annotation on ≥20%; target Cohen's κ ≥ 0.7 for risk; adjudication by senior clinician.
- Annotator wellbeing: rotation, limits on exposure to distressing content, debriefs.

## 8. Training & Tuning

| Component | Method |
|---|---|
| C4 risk classifier | Fine-tune multilingual encoder; class-weighted loss; threshold calibration for recall ≥ 0.95 on tiers ≥ 3 |
| C6–C8 | Fine-tune small encoders; distil from LLM labels + human verification |
| C12 generator | Phase 1: prompt engineering + few-shot. Phase 2: SFT and preference tuning (DPO) on clinician-rated pairs, if provider supports, or on an open-weight model |
| C13 guard | Fine-tuned classifier + rule engine |
| Continuous | Monthly retraining from reviewed edge cases; red-team findings added to training & eval sets |

## 9. Evaluation Plan

### 9.1 Offline suites (release gate)
| Suite | Size (initial) | Metric | Gate |
|---|---|---|---|
| Risk golden set | 3,000 msgs (balanced, multilingual) | Recall tier≥3; FNR tier 4 | Recall ≥ 0.95; tier-4 FNR ≤ 1% |
| Risk calibration | same | ECE | ≤ 0.05 |
| Red-team adversarial | 1,000 prompts | Harmful-output rate | 0 critical; < 0.5% minor |
| Rule-violation suite | 500 | Violation rate per rule R1–R10 | ≤ 0.5% each; R3 = 0 |
| Empathy/quality | 300 conversations | Clinician rating (1–5) | Mean ≥ 4.0 |
| Exercise fidelity | All protocols × 3 languages | Steps delivered correctly | ≥ 98% |
| Grounding/factuality | 300 psychoed Qs | Unsupported claims | ≤ 2% |
| Fairness | Sliced by language, gender, region | Metric gap | Risk recall gap ≤ 3 pts |
| Latency/cost | Load test | p95, ₹/session | Within budget |

### 9.2 Online monitoring
- Risk tier distribution drift, escalation rates, guardrail block/rewrite rates.
- User feedback ("felt unsafe", thumbs-down) → triage queue.
- Weekly clinician audit of random sample (≥ 200 conversations, de-identified) + all tier ≥3 events.
- Outcome metrics (PHQ-9/GAD-7 trajectories) by cohort.

### 9.3 Red-teaming programme
- Internal + external red teamers incl. clinicians, people with lived experience, Indic-language speakers.
- Themes: method seeking, jailbreaks, role-play bypass, gradual escalation, minors, self-harm communities slang, eating-disorder "tips", violence, misinformation about medication.
- Before every major model/prompt change and quarterly.

## 10. Model Governance

- **Model card** per release: intended use, out-of-scope uses, training data summary, eval results, known limitations.
- **Change control**: any change to model, prompt, classifier threshold, or crisis template requires: eval suite pass → clinical lead approval → staged rollout.
- **Versioning**: every message records `model_version`, `prompt_version`, `classifier_versions`.
- **Incident linkage**: safety incidents traced to exact versions for root-cause analysis.

## 11. Known Limitations (to communicate transparently)
- May misread sarcasm, idioms, or very indirect distress.
- Lower accuracy in languages/dialects with less training data.
- Cannot verify identity, age, or physical safety.
- Not suitable for severe mental illness or emergencies.
