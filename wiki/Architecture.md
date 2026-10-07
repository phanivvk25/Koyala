# Architecture

Full design: [TDD](https://github.com/phanivvk25/Koyala/blob/main/docs/04-TDD-Technical-Design.md). This page describes what is built today.

## Principles

1. **Safety path is independent** — risk detection and crisis resources work even if the AI model is down.
2. **Deterministic where it matters** — crisis replies and exercises are fixed content; the AI model never improvises them.
3. **Privacy by design** — personal details are removed before text reaches the AI model; stored content is encrypted per user.
4. **Fail safe** — when a detector fails, assume more risk, not less.

## Every chat message

```
User message
   │
   ▼
Risk assessment (every message, before anything else)
   lexicon ─┐
   judge ───┼─► max() ─► tier 0–4   (+ sticky floor from recent risk, PHQ-9 floor)
   floors ──┘            detector error → tier 2
   │
   ├── tier ≥ 3 ──► approved crisis template + helplines + "talk to a counsellor"
   │                (AI model NOT called)
   ├── tier 2 ───► AI model asked to gently explore risk; helplines shown
   ├── active exercise ─► next step from the exercise engine
   ├── asks for help calming down ─► offer exercises
   └── otherwise ─► AI model reflects and asks an open question
                        │
                        ▼
                Output guard (diagnosis, dosage, "I'm human", links, numbers)
                fail → regenerate once → fail → safe fallback message
```

## Code map (`backend/koyala/`)

| Path | Responsibility |
|---|---|
| `main.py` | App factory; picks stores, AI model and risk judge from [[Configuration]] |
| `api/` | HTTP endpoints — see [[API Reference]] |
| `auth/` | Anonymous accounts, access tokens, rotating refresh tokens |
| `safety/` | Lexicon, risk assessor, risk state, crisis templates, LLM risk judge |
| `dialogue/` | Per-turn orchestrator, AI model providers, prompts, output guard, redaction |
| `protocols/` | Exercise engine (YAML-defined) |
| `assessments/` | PHQ-9, GAD-7, WHO-5 scoring |
| `tracking.py` | Mood, journal, assessments, safety plan, check-ins |
| `escalation.py` | Counsellor handoff, paging, SLA |
| `followups.py` | Follow-up check-ins after elevated risk |
| `privacy.py` | Data export and account deletion |
| `db/` | SQLAlchemy models, Alembic migrations, encryption, SQL stores |
| `evals/` | Risk-detection evaluation harness |
| `content/` | Crisis templates, helplines, exercises (**placeholder content**) |
| `jobs.py` | Scheduled jobs — see [[Background Jobs]] |

## Storage

Every store has an in-memory version (development, tests) and a PostgreSQL version selected by `KOYALA_DATABASE_URL`. See [[Database and Migrations]].
