# Koyala backend (MVP scaffold)

Python/FastAPI implementation of the safety-critical core described in
[`docs/04-TDD-Technical-Design.md`](../docs/04-TDD-Technical-Design.md).

## What's here

| Module | Purpose | Spec |
|---|---|---|
| `koyala/safety/` | Risk lexicon, risk aggregation (tiers 0–4), sticky risk state, crisis templates, helpline directory | AI Spec §4, Safety Protocol §4–6 |
| `koyala/dialogue/` | Per-turn orchestrator, LLM provider interface, system prompt, output guard, intent | TDD §4, AI Spec §5–6 |
| `koyala/protocols/` | Deterministic exercise engine (YAML-defined) | TDD §7.3 |
| `koyala/assessments/` | PHQ-9 / GAD-7 / WHO-5 scoring, PHQ-9 item-9 flag | PRD FR-ONB-06/09 |
| `koyala/api/` | REST API v1 | TDD §7.1 |
| `koyala/auth/` | Anonymous sign-up, JWT access tokens, rotating refresh tokens with reuse detection | PRD FR-ONB-04, TDD §9 |
| `koyala/db/` | PostgreSQL schema, Alembic migrations, SQL stores, envelope encryption | TDD §6, §9 |
| `koyala/content/` | Crisis templates, helplines, exercises (**placeholder — needs clinical approval**) | Safety Protocol §5 |

## Safety guarantees enforced in code (and tested)

- Risk is assessed on **every** message before any response is generated.
- Tier ≥ 3 returns an approved crisis template; **the LLM is never called**.
- Tier 2 forces a risk-exploration response with helplines attached.
- A failing risk detector **fails safe** to tier 2.
- High risk is sticky (floored for 72 h); PHQ-9 item 9 > 0 floors risk for 14 days.
- Every LLM reply passes the output guard (diagnosis, dosage, human claims, URLs, unapproved numbers); regenerate once, then safe fallback.
- LLM outage → fallback template with helplines.

## Risk evaluation

```bash
python -m koyala.evals.risk_eval            # markdown report on the starter set
python -m koyala.evals.risk_eval my.jsonl   # any labelled set (see evals/data/README.md)
python -m koyala.evals.risk_eval --enforce-gates   # exit 1 unless release gates pass
```

Reports high-risk recall (gate ≥ 95%), imminent miss rate (gate ≤ 1%), false
alarms, per-language and per-style recall, the confusion matrix and every missed
message. CI writes the report to the job summary.

**Current result on the synthetic starter set: the lexicon fails every release
gate** (≈ 52% high-risk recall; 64% of imminent messages missed; 0% of coded
phrasing such as "kms"). The starter set was written by engineering and is not a
clinical measure — a clinician-labelled golden set and a trained classifier (C4)
are required before launch. `tests/test_risk_eval.py` pins today's numbers as a
no-regression floor.

## Authentication

```
POST /v1/auth/anonymous            → {user_id, access_token, refresh_token, expires_in}
POST /v1/auth/refresh  {refresh_token} → new pair (old refresh token is consumed)
POST /v1/auth/logout   {refresh_token} → 204, revokes that sign-in's tokens
```

- User endpoints require `Authorization: Bearer <access_token>`; the user id always
  comes from the token.
- Access tokens: HS256 JWT, 15 minutes. Refresh tokens: opaque, 30 days, single use,
  stored only as SHA-256 hashes. Replaying a used refresh token revokes its whole
  family (that device's sign-in) and returns 401.
- `KOYALA_JWT_SECRET` (≥ 32 bytes) is required with a database; without one a random
  dev secret is generated at startup.
- Not yet: phone OTP / email sign-in (needs an SMS provider), rate limiting on
  sign-up (planned at the API gateway, TDD §3).

## Run

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q
uvicorn koyala.main:app --reload   # needs: pip install uvicorn
```

### Using PostgreSQL

Without `KOYALA_DATABASE_URL` the app uses in-memory storage (lost on restart).

```bash
docker compose up -d db                       # from the repo root
cp .env.example .env && set -a && . ./.env && set +a
export KOYALA_MASTER_KEY=$(python -c "from koyala.db.crypto import Crypto; print(Crypto.generate_key())")
python -m koyala.db.migrate                   # apply migrations
uvicorn koyala.main:app --reload
```

| Table | Contents |
|---|---|
| `users` | User id + per-user data key (wrapped by the master key) |
| `chat_sessions` | Session metadata; active exercise state (**encrypted**) |
| `messages` | Conversation history (**encrypted**, AES-256-GCM, bound to the user) |
| `risk_states` | Sticky risk floor, PHQ-9 floor, follow-up due time |
| `risk_events` | Audit trail of tier ≥ 2 turns (tier + categories, no content) |

Schema changes: edit `koyala/db/models.py`, then
`alembic revision --autogenerate -m "..."` and review the generated file.
Tests check the migrations match the models, on SQLite always and on
PostgreSQL when `KOYALA_TEST_DATABASE_URL` is set (CI does this).

### Using Claude as the model

```bash
export KOYALA_LLM_PROVIDER=anthropic     # default is "stub" (offline)
export ANTHROPIC_API_KEY=...              # or an `ant auth login` profile
export KOYALA_LLM_MODEL=claude-opus-5-5   # optional (default)
export KOYALA_LLM_EFFORT=medium           # optional: low | medium | high
```

- Text is PII-redacted (emails, phones, URLs, Aadhaar/PAN-like IDs) before it is sent.
- Server-side refusal fallback (`fallbacks: "default"`) is enabled.
- Any API error, timeout, refusal or empty reply → safe fallback template with helplines.
- Before production: confirm data-retention terms with Anthropic and data-transfer
  compliance under DPDP (docs/07 §7).

## Not yet production-ready

- **Auth**: anonymous accounts only; phone/email sign-in and sign-up rate limiting still to do.
- **Storage**: PostgreSQL supported; master key is an env var and should move to a cloud KMS. Assessments, mood logs, journal and safety plans are not stored yet.
- **LLM**: Claude provider available; redaction does not yet cover person/place names (needs NER).
- **Risk classifier (C4)**: interface only; lexicon is a placeholder needing clinical/linguistic review.
- **Content**: all crisis text, helplines and exercises must be clinically approved and verified.
