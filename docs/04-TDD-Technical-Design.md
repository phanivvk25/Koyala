# Koyala — Technical Design Document (TDD)

| Field | Value |
|---|---|
| Document | TDD v0.1 (Draft) |
| Depends on | PRD (03) |
| Related | AI Model Spec (05), Safety Protocol (06), Compliance (07) |
| Status | Draft for review |

---

## 1. Purpose & Scope

Describes **how** Koyala is built: system architecture, services, data model, APIs, infrastructure, security controls and operational practices needed to meet the PRD's functional and non-functional requirements. AI/ML internals are detailed in doc 05.

## 2. Architecture Principles

1. **Safety path is independent** — risk detection and crisis resources must work even if the LLM provider is down.
2. **Deterministic where it matters** — crisis responses and exercise protocols are data-driven state machines; the LLM only phrases content.
3. **Privacy by design** — minimise, encrypt, segregate identity from content.
4. **Vendor-agnostic AI** — LLM/ASR/TTS behind an internal gateway; swappable.
5. **Observable & auditable** — every risk decision is traceable.
6. **Low-end device friendly** — thin client, small payloads, offline cache for safety content.

## 3. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Clients                                                                  │
│  Android/iOS app (React Native)  ·  Web app (Next.js)                    │
│  Clinician portal (Next.js)      ·  Org admin portal (Next.js)           │
└───────────────┬──────────────────────────────────────────────────────────┘
                │ HTTPS / WSS (TLS 1.3)
┌───────────────▼──────────────────────────────────────────────────────────┐
│ Edge: CDN + WAF + API Gateway (rate limit, auth, request IDs)            │
└───────────────┬──────────────────────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────────────────────┐
│ Core services (containers on Kubernetes, India region)                   │
│                                                                          │
│  auth-svc        identity, anonymous accounts, OTP, SSO (Phase 3)        │
│  consent-svc     consent records, versions, revocation                   │
│  profile-svc     preferences, goals, language                            │
│  conversation-svc  session orchestration (WebSocket), message store      │
│  safety-svc  ★   risk classifiers, risk state, crisis flow, escalation   │
│  dialogue-svc    intent/emotion, policy, protocol engine, memory         │
│  ai-gateway      LLM/ASR/TTS routing, prompt mgmt, guardrails, PII redact│
│  content-svc     exercises, psychoeducation, crisis templates, RAG index │
│  tracking-svc    mood logs, assessments (PHQ-9/GAD-7/WHO-5), insights    │
│  journal-svc     journal entries (private flag)                          │
│  notify-svc      push/SMS/email, reminders, quiet hours                  │
│  clinician-svc   links, dashboards, homework, notes (Phase 3)            │
│  org-svc         org tenancy, codes, aggregate analytics (Phase 3)       │
│  escalation-svc  handoff to counsellor partner, on-call paging           │
│  billing-svc     subscriptions, payments (Phase 2)                       │
│  privacy-svc     export, deletion, DSR workflows                         │
└───────────────┬──────────────────────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────────────────────┐
│ Data layer                                                               │
│  PostgreSQL (identity DB)  ║  PostgreSQL (clinical/content DB, encrypted)│
│  Redis (session state, risk state cache)                                 │
│  Vector DB (pgvector) — content embeddings only, NO user data            │
│  Object storage (audio, exports) — encrypted, lifecycle rules            │
│  Event bus (Kafka/PubSub) → analytics warehouse (de-identified)          │
│  Audit log store (append-only / WORM)                                    │
└──────────────────────────────────────────────────────────────────────────┘
External: LLM provider (zero retention) · ASR/TTS · SMS/OTP · Push (FCM/APNs)
          · Crisis partner (API/telephony) · Payment gateway
```

## 4. Message Processing Pipeline (per user turn)

```
1. Client → conversation-svc (WSS)  [msg, session_id, client_ts]
2. conversation-svc: persist encrypted msg; fetch session context
3. PARALLEL:
   a. safety-svc.assess(msg, recent_context, risk_state)   ← hard deadline 300 ms
   b. dialogue-svc.understand(msg) → intent, emotions, distortions, entities
4. If risk_tier ≥ 3  → safety-svc.crisis_flow()  (template response, escalation)
                        SKIP free generation. Return.
   If risk_tier == 2 → dialogue policy forced to "risk_explore" action
5. dialogue-svc.policy() → next_action (reflect | ask | teach | exercise_step | summarise | redirect)
6. If exercise_step → protocol engine gives step content; LLM paraphrases within constraints
7. ai-gateway.generate(system_prompt + policy + retrieved content + memory + history)
8. ai-gateway.output_guard(response)  → safety re-check, policy check, PII check
      fail → regenerate once with stricter prompt → fail again → safe fallback template
9. Stream response to client; persist; emit de-identified events
10. Async: memory summariser, insight updates, clinician flags (if linked)
```

**Failure modes**
| Failure | Behaviour |
|---|---|
| LLM timeout / outage | Fallback: "I'm having trouble responding right now" + offer exercises + helplines; safety-svc still runs |
| safety-svc timeout | **Fail-safe**: treat as tier 2 (show resources inline), log incident, page on-call |
| Network loss on client | Offline cache: helplines, safety plan, 5 core exercises |

## 5. Service Details

### 5.1 safety-svc (critical)
- Inputs: current message, last N turns, user risk history, assessment scores.
- Components: keyword/lexicon fast-path (multilingual, incl. transliterations) → ML risk classifier → LLM risk judge (for tiers 1–3 ambiguity) → tier aggregator (max-of with calibrated thresholds).
- Outputs: `risk_tier (0–4)`, `risk_categories[]` (self_harm, suicide, harm_others, abuse, medical_emergency, psychosis_signs, eating_disorder, substance), `confidence`, `rationale_id`.
- Maintains `risk_state` per user (current tier, decay schedule, last escalation).
- Triggers `escalation-svc` and `notify-svc` according to Safety Protocol (06).
- Runs with separate deployment, separate on-call, separate SLOs (99.95%).

### 5.2 dialogue-svc
- **Understanding**: intent classifier, emotion classifier, distortion tagger, entity extractor.
- **Policy**: rule + learned policy selecting next therapeutic action using user state (goal, programme step, risk, engagement, preferences).
- **Protocol engine**: executes exercises defined in YAML (see §7.3).
- **Memory manager**: short-term (session window), long-term (structured profile + session summaries) — only with consent.

### 5.3 ai-gateway
- Provider abstraction (primary + fallback LLM).
- Prompt registry with versioning; every response logs `prompt_version`, `model_version`.
- PII redaction before sending to external providers (names, phone, address, emails → placeholders; re-hydrated client-side when necessary).
- Output guardrails (see doc 05 §6).
- Token/cost metering per session; budget caps.

### 5.4 content-svc
- CMS for clinicians with review workflow: Draft → Clinical Review → Approved → Published → Scheduled re-review.
- Stores exercises (protocol YAML), psychoeducation articles, crisis templates, helpline directory (by state/language).
- Builds RAG index (embeddings of approved content only).

### 5.5 escalation-svc
- Integrates with crisis partner via API (chat handoff) and telephony (click-to-call / callback).
- Shares only **minimum necessary** context with consent: first name/alias, language, risk tier, brief AI summary.
- Tracks SLA: request → counsellor connected; alerts on-call if > 5 min.

## 6. Data Model (core entities)

```
users(id, created_at, auth_type[anon|phone|email|sso], age_confirmed, locale, status)
identity(user_id, phone_enc, email_enc, name_enc)             -- identity DB
consents(id, user_id, purpose, version, granted_at, revoked_at)
profiles(user_id, language, tone, goals[], timezone, region_state)
sessions(id, user_id, started_at, ended_at, mode, summary_enc)
messages(id, session_id, role[user|assistant|system], content_enc, created_at,
         risk_tier, intent, emotions[], model_version, prompt_version)
risk_events(id, user_id, message_id, tier, categories[], action_taken, reviewer_id, outcome)
risk_state(user_id, current_tier, updated_at, next_followup_at)
safety_plans(user_id, warning_signs_enc, coping_enc, contacts_enc, professionals_enc, env_safety_enc)
assessments(id, user_id, instrument[PHQ9|GAD7|WHO5|ISI], item_scores[], total, taken_at)
mood_logs(id, user_id, score, emotions[], factors{}, note_enc, logged_at)
journal_entries(id, user_id, content_enc, private_flag, created_at)
exercise_runs(id, user_id, exercise_id, version, started_at, completed_at, pre_distress, post_distress)
memories(id, user_id, type[goal|trigger|strategy|fact], content_enc, source_session_id, user_editable)
clinician_links(id, user_id, clinician_id, scopes[], consented_at, revoked_at)     -- Phase 3
orgs(id, name, settings), org_memberships(user_id, org_id)                          -- Phase 3
audit_log(id, actor, action, resource, ts, ip_hash)                                  -- append-only
```

- `*_enc` fields: application-level envelope encryption (per-user data key, wrapped by KMS).
- Identity DB and clinical DB are separate; join only via `user_id` in trusted services.
- Org analytics consume only de-identified, aggregated events.

## 7. Key APIs & Formats

### 7.1 Public API (selected)
```
POST /v1/auth/anonymous                → {user_id, token}
POST /v1/consents                      {purpose, version, granted}
GET  /v1/profile  | PATCH /v1/profile
WS   /v1/chat?session_id=…            client→ {type:"msg", text|audio_ref}
                                       server→ {type:"delta"|"final"|"crisis"|"exercise_step", …}
POST /v1/assessments                   {instrument, item_scores[]}
POST /v1/mood                          {score, emotions[], factors{}, note}
GET  /v1/insights?range=30d
GET  /v1/exercises | POST /v1/exercises/{id}/runs
GET  /v1/safety/resources?state=TS&lang=te
PUT  /v1/safety/plan
POST /v1/escalations                   (user-initiated "talk to a person")
GET  /v1/privacy/export | DELETE /v1/privacy/account
```

### 7.2 Crisis server event
```json
{
  "type": "crisis",
  "tier": 3,
  "template_id": "crisis_t3_v4_te",
  "message": "<approved localised text>",
  "actions": [
    {"kind": "call", "label": "Tele-MANAS 14416", "number": "14416"},
    {"kind": "handoff", "label": "Talk to a counsellor now"},
    {"kind": "safety_plan"}
  ]
}
```

### 7.3 Exercise protocol definition (example)
```yaml
id: grounding_54321
version: 3
title: { en: "5-4-3-2-1 Grounding", hi: "...", te: "..." }
indications: [anxiety, panic, dissociation_mild]
contraindications: []
duration_min: 3
pre_measure: distress_0_10
steps:
  - id: intro
    script_key: grounding.intro
    llm_paraphrase: allowed
  - id: see_5
    script_key: grounding.see5
    expects: user_text
    validator: count_items>=3          # gentle encouragement if fewer
  - id: hear_4
    script_key: grounding.hear4
  - id: touch_3
    script_key: grounding.touch3
  - id: smell_2
    script_key: grounding.smell2
  - id: taste_1
    script_key: grounding.taste1
  - id: close
    script_key: grounding.close
post_measure: distress_0_10
on_distress_increase: offer_alternative_or_talk
clinical_owner: "<reviewer>"
review_due: 2027-10-01
```

## 8. Technology Stack

| Layer | Choice (proposed) | Notes |
|---|---|---|
| Mobile | React Native (TypeScript) | Single codebase; small bundle; offline storage (encrypted SQLite) |
| Web / portals | Next.js (TypeScript) | |
| Backend | Python (FastAPI) for AI-adjacent services; TypeScript/Node or Python for CRUD services | Keep to one language if team is small (Python) |
| Realtime | WebSockets via gateway | SSE fallback |
| DB | PostgreSQL 16 + pgvector | Managed, India region, encrypted |
| Cache | Redis | Risk state, sessions |
| Queue | Kafka / Cloud Pub/Sub | Events, async jobs |
| ML serving | PyTorch / ONNX Runtime on CPU/GPU nodes | Classifiers |
| LLM | Hosted frontier model via API (zero retention, India/enterprise terms) + fallback provider | See doc 05 |
| Speech | Cloud ASR/TTS with Indic support | Evaluate per language |
| Infra | Kubernetes, Terraform, India cloud region | Multi-AZ |
| Secrets | Cloud KMS + secret manager | Per-user data keys |
| Observability | OpenTelemetry, Prometheus/Grafana, LLM tracing (self-hosted) | No raw content in logs |
| CI/CD | GitHub Actions, IaC, staged deploys, safety eval gate | |

## 9. Security Architecture

- **AuthN**: short-lived JWT (15 min) + refresh token; device binding for anonymous accounts; OTP for phone; SSO (SAML/OIDC) for orgs.
- **AuthZ**: RBAC + ABAC (clinician access only via active `clinician_links` scopes).
- **Encryption**: TLS 1.3; AES-256 at rest; envelope encryption for sensitive fields; key rotation yearly.
- **Segregation**: identity vs clinical DB; analytics warehouse holds only pseudonymous IDs.
- **Logging**: no message content in app logs; content access only through audited break-glass.
- **Client**: app lock (PIN/biometric), encrypted local storage, screenshot blocking on sensitive screens (Android `FLAG_SECURE`), certificate pinning.
- **AppSec**: SAST/DAST, dependency scanning, annual third-party pen test, bug bounty (Phase 3).
- **Prompt-injection defence**: user input never treated as system instruction; retrieved content only from approved store; tool use disabled for LLM in user-facing path.

## 10. Observability & SLOs

| SLO | Target |
|---|---|
| Crisis resource availability (in-app) | 99.95% |
| safety-svc p99 latency | < 500 ms |
| Chat first-token p95 | < 2 s |
| Escalation connect p90 | < 5 min |
| Error budget policy | Freeze feature deploys if safety SLO breached |

Dashboards: risk tier distribution, escalation funnel, guardrail block rates, model latency/cost, exercise completion. Alerts route to on-call engineering + on-call clinical lead for safety anomalies.

## 11. Environments & Deployment

- `dev` → `staging` (synthetic data only) → `prod`.
- **Release gate**: every model/prompt/content change runs the safety evaluation suite (doc 05 §8) — must pass thresholds before promotion.
- Canary 5% → 25% → 100% with automated rollback on safety or error metrics.
- Infrastructure as code; no manual prod changes.

## 12. Data Retention (defaults; see doc 07)

| Data | Retention |
|---|---|
| Messages | Until user deletes, or 24 months inactivity → delete |
| Risk events & audit logs | 7 years (legal/safety), minimised content |
| Audio | Deleted after transcription (≤ 24 h) unless user opts to keep |
| Analytics events | De-identified, 3 years |
| Deleted accounts | Hard delete within 30 days; backups roll off within 35 days |

## 13. Testing Strategy

- Unit + integration tests per service; contract tests between services.
- Protocol engine tests: each exercise YAML validated & simulated.
- Safety regression suite (golden conversations, red-team set) in CI.
- Load tests for 10k concurrent sessions.
- Chaos tests: LLM outage, safety-svc slowdown → verify fail-safe behaviour.
- Localisation QA by native-speaking clinicians.
- Accessibility testing (TalkBack/VoiceOver).

## 14. Open Technical Questions
1. Single-language backend (Python) vs polyglot?
2. Self-host a smaller open-weight model for routine turns to cut cost?
3. Which ASR/TTS vendor gives best Telugu/Hindi quality on low bandwidth?
4. Crisis partner integration method (API vs telephony bridge)?
