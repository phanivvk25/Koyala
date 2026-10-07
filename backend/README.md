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
| `koyala/content/` | Crisis templates, helplines, exercises (**placeholder — needs clinical approval**) | Safety Protocol §5 |

## Safety guarantees enforced in code (and tested)

- Risk is assessed on **every** message before any response is generated.
- Tier ≥ 3 returns an approved crisis template; **the LLM is never called**.
- Tier 2 forces a risk-exploration response with helplines attached.
- A failing risk detector **fails safe** to tier 2.
- High risk is sticky (floored for 72 h); PHQ-9 item 9 > 0 floors risk for 14 days.
- Every LLM reply passes the output guard (diagnosis, dosage, human claims, URLs, unapproved numbers); regenerate once, then safe fallback.
- LLM outage → fallback template with helplines.

## Run

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q
uvicorn koyala.main:app --reload   # needs: pip install uvicorn
```

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

- **Auth**: callers pass `X-User-Id`; replace with real auth before any deployment.
- **Storage**: in-memory; move to PostgreSQL with encrypted content columns.
- **LLM**: Claude provider available; redaction does not yet cover person/place names (needs NER).
- **Risk classifier (C4)**: interface only; lexicon is a placeholder needing clinical/linguistic review.
- **Content**: all crisis text, helplines and exercises must be clinically approved and verified.
