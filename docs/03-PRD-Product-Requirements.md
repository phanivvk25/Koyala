# Koyala — Product Requirements Document (PRD)

| Field | Value |
|---|---|
| Document | PRD v0.1 (Draft) |
| Depends on | MRD (01), BRD (02) |
| Feeds into | TDD (04), AI Model Spec (05), Safety Protocol (06), Compliance (07) |
| Status | Draft for review |

---

## 1. Overview

**Koyala** is an AI mental health companion that offers private, culturally aware, evidence-based emotional support in English and Indian languages, detects risk, and connects people to human care when needed.

### 1.1 Goals
- G1: Give users a safe place to talk and feel heard, 24×7.
- G2: Teach practical, evidence-based coping skills.
- G3: Help users notice patterns via mood & outcome tracking.
- G4: Detect risk early and route to human help reliably.
- G5: (Phase 3) Extend therapists' reach between sessions.

### 1.2 Non-goals
- Diagnosing conditions or recommending/adjusting medication.
- Replacing therapy or emergency services.
- Serving users under 18 (initial releases).
- Managing severe mental illness (refer out).

## 2. Personas

| Persona | Snapshot | Primary needs |
|---|---|---|
| **Priya, 21, engineering student, Hyderabad** | Exam stress, homesick, speaks Telugu/English mix | Late-night support, quick calming tools, no stigma |
| **Rahul, 29, software engineer, Bengaluru** | Burnout, poor sleep | Short practical tools, sleep help, privacy from employer |
| **Meena, 42, homemaker, Lucknow** | Low mood, isolation, prefers Hindi voice | Voice, simple UI, warm tone |
| **Dr. Kavya, clinical psychologist** | 30 clients/week | See client progress between sessions, assign homework |
| **Arjun, HR head** | Wants wellbeing benefit | Adoption & aggregate impact, no privacy liability |

## 3. User Stories (selected; full backlog in tracker)

### Epic E1 — Onboarding & Consent
- US-1.1 As a new user, I want to understand what Koyala is and isn't, so I can trust it.
- US-1.2 As a privacy-conscious user, I want to start without giving my name or phone number.
- US-1.3 As a user, I want to choose my language and how Koyala talks to me.
- US-1.4 As a user, I want a quick check of how I'm doing (PHQ-9/GAD-7) so the app can tailor support.

### Epic E2 — Conversation
- US-2.1 As a stressed user, I want to vent and feel heard without being lectured.
- US-2.2 As a user, I want Koyala to remember what I shared before (if I allow it).
- US-2.3 As a user who types in Hinglish/Tenglish, I want to be understood.
- US-2.4 As a user, I want to speak instead of type.

### Epic E3 — Exercises & Programmes
- US-3.1 As an anxious user, I want a guided breathing/grounding exercise in under 3 minutes.
- US-3.2 As a user with negative thoughts, I want to work through a thought record.
- US-3.3 As a user with poor sleep, I want a structured multi-week sleep programme.

### Epic E4 — Tracking & Insights
- US-4.1 As a user, I want to log my mood in one tap.
- US-4.2 As a user, I want to see trends and what seems to affect my mood.

### Epic E5 — Safety
- US-5.1 As a user in distress, I want a visible "Get help now" button at all times.
- US-5.2 As a user at risk, I want to be connected to a real person quickly.
- US-5.3 As a user, I want to create a safety plan I can open anytime.

### Epic E6 — Human Care (Phase 2–3)
- US-6.1 As a user, I want to book a session with a licensed therapist.
- US-6.2 As a therapist, I want to see my client's mood/PHQ-9 trends and homework adherence (with client consent).
- US-6.3 As a therapist, I want AI-drafted session notes that I review and sign.

### Epic E7 — Organisation (Phase 3)
- US-7.1 As an HR admin, I want to invite employees via codes/SSO.
- US-7.2 As an HR admin, I want aggregate engagement and wellbeing trends, never individual data.

### Epic E8 — Privacy Controls
- US-8.1 As a user, I want to view, export and delete my data.
- US-8.2 As a user, I want to turn off AI memory or mark journal entries private.

## 4. Functional Requirements

Priority: **M** Must (MVP), **S** Should (Phase 2), **C** Could (Phase 3+).

### 4.1 Onboarding & Account (FR-ONB)

| ID | Requirement | Pri |
|---|---|---|
| FR-ONB-01 | Show a plain-language explainer: Koyala is an AI, not a therapist or emergency service; data use summary | M |
| FR-ONB-02 | Obtain granular, itemised consent (core processing, AI memory, research use, clinician sharing) — each separately revocable | M |
| FR-ONB-03 | Age confirmation; block <18 with a supportive message and youth helpline info | M |
| FR-ONB-04 | Support anonymous account (device-bound) and optional upgrade to phone/email login | M |
| FR-ONB-05 | Language selection (EN + 2 Indic at MVP) and tone preference (gentle / direct / structured) | M |
| FR-ONB-06 | Baseline check-in: WHO-5 always; PHQ-9 and GAD-7 offered (skippable) | M |
| FR-ONB-07 | Goal selection (stress, anxiety, low mood, sleep, relationships, self-esteem, other) | M |
| FR-ONB-08 | Optional emergency contact and location (state/city) for localised helplines | M |
| FR-ONB-09 | If PHQ-9 item 9 > 0, immediately trigger risk assessment flow (see Safety Protocol) | M |

### 4.2 Conversation (FR-CHAT)

| ID | Requirement | Pri |
|---|---|---|
| FR-CHAT-01 | Text chat with streaming responses, p95 first token < 2 s | M |
| FR-CHAT-02 | Every user message passes through the risk layer before a response is generated | M |
| FR-CHAT-03 | Support modes: Listen, Skill, Learn, Check-in — auto-selected by intent, user can switch | M |
| FR-CHAT-04 | Understand code-mixed and transliterated input (e.g., Hindi in Latin script) | M |
| FR-CHAT-05 | Respond in the user's chosen language/script | M |
| FR-CHAT-06 | Session opening ("What would help most today?") and closing (summary + one small next step) | M |
| FR-CHAT-07 | Long-term memory of goals, triggers, helpful strategies — only with consent; user-viewable and editable | S |
| FR-CHAT-08 | Voice input (ASR) and voice output (TTS) | S |
| FR-CHAT-09 | Disclose AI identity whenever asked and in the chat header at all times | M |
| FR-CHAT-10 | Out-of-scope handling (medical, legal, financial questions) with gentle redirection | M |
| FR-CHAT-11 | Thumbs up/down + "this wasn't helpful / felt unsafe" report on each response | M |
| FR-CHAT-12 | Offline graceful degradation: show saved exercises & helplines when no network | M |

### 4.3 Exercises & Programmes (FR-EX)

| ID | Requirement | Pri |
|---|---|---|
| FR-EX-01 | Library of ≥15 clinician-approved exercises at MVP (breathing ×3, grounding, PMR, body scan, thought record, behavioural activation, worry time, problem-solving, self-compassion, gratitude, values, sleep hygiene, STOP skill) | M |
| FR-EX-02 | Each exercise defined as a structured protocol (steps, prompts, timing, contraindications) executed by the protocol engine | M |
| FR-EX-03 | AI suggests exercises based on intent, emotion, and history; user can browse directly | M |
| FR-EX-04 | Multi-week programmes (Anxiety 6-week CBT, Sleep 4-week CBT-I-informed, Low mood 6-week BA) | S |
| FR-EX-05 | Audio guidance for relaxation exercises in each supported language | S |
| FR-EX-06 | Post-exercise rating (distress 0–10 before/after) | M |

### 4.4 Tracking & Insights (FR-TRK)

| ID | Requirement | Pri |
|---|---|---|
| FR-TRK-01 | One-tap mood log (5-point) + optional emotion tags + note | M |
| FR-TRK-02 | Optional factors: sleep hours, exercise, social contact, caffeine/alcohol, period | M |
| FR-TRK-03 | PHQ-9 / GAD-7 re-assessment every 14 days (reminder, skippable) | M |
| FR-TRK-04 | Trend charts (7/30/90 days) | M |
| FR-TRK-05 | AI-generated weekly insight (correlational, non-diagnostic language) | S |
| FR-TRK-06 | Wearable/health-platform import (sleep, steps) with opt-in | C |

### 4.5 Journal (FR-JRN)

| ID | Requirement | Pri |
|---|---|---|
| FR-JRN-01 | Free-form and prompted journaling | M |
| FR-JRN-02 | Per-entry "private" toggle excludes it from all AI processing | M |
| FR-JRN-03 | Optional AI reflection on an entry (themes, strengths) | S |

### 4.6 Safety (FR-SAFE) — see doc 06 for full protocol

| ID | Requirement | Pri |
|---|---|---|
| FR-SAFE-01 | Persistent "Get help now" button on every screen, max 1 tap to helplines | M |
| FR-SAFE-02 | Localised helpline directory (Tele-MANAS 14416, emergency 112, partner line) | M |
| FR-SAFE-03 | Risk tiering (0–4) on every turn; tier ≥3 switches to scripted crisis flow | M |
| FR-SAFE-04 | Warm handoff to a human counsellor (chat/call) for tier ≥3, target connect < 5 min | M |
| FR-SAFE-05 | Safety plan builder (Stanley–Brown) accessible offline | M |
| FR-SAFE-06 | Sticky risk state: elevated follow-up check-in within 24 h after tier ≥2 | M |
| FR-SAFE-07 | Trusted-contact alert only with prior explicit consent (or as legally required) | S |
| FR-SAFE-08 | Detection of harm-to-others, abuse (incl. domestic/child abuse), medical emergencies → appropriate resources | M |

### 4.7 Human Care & Clinician Portal (FR-CLIN) — Phase 2/3

| ID | Requirement | Pri |
|---|---|---|
| FR-CLIN-01 | Therapist directory & booking with partner network | S |
| FR-CLIN-02 | Client–clinician linking via invite code with explicit, revocable consent | C |
| FR-CLIN-03 | Dashboard: mood/PHQ-9/GAD-7 trends, exercise adherence, risk flags | C |
| FR-CLIN-04 | Assign exercises/programmes as homework | C |
| FR-CLIN-05 | AI-drafted pre-session brief and post-session SOAP/DAP note; clinician must edit/approve | C |
| FR-CLIN-06 | Risk alert inbox with acknowledgement tracking | C |

### 4.8 Organisation Admin (FR-ORG) — Phase 3

| ID | Requirement | Pri |
|---|---|---|
| FR-ORG-01 | Invite via codes / SSO (SAML/OIDC) | C |
| FR-ORG-02 | Aggregate dashboard with k-anonymity ≥10; no free-text, no individual data | C |
| FR-ORG-03 | Customisable resources page (EAP numbers, policies) | C |

### 4.9 Privacy Controls (FR-PRIV)

| ID | Requirement | Pri |
|---|---|---|
| FR-PRIV-01 | View & export all personal data (JSON + PDF) | M |
| FR-PRIV-02 | Delete account & data (hard delete within 30 days, except legally required logs) | M |
| FR-PRIV-03 | Toggle AI memory, research consent, clinician sharing at any time | M |
| FR-PRIV-04 | App lock (PIN/biometric) and discreet app icon/notification option | M |

### 4.10 Engagement (FR-ENG)

| ID | Requirement | Pri |
|---|---|---|
| FR-ENG-01 | User-scheduled reminders (check-in, exercise) | M |
| FR-ENG-02 | No streak-loss shaming, no guilt-based notifications, quiet hours respected | M |
| FR-ENG-03 | Gentle nudge to human connection if usage pattern suggests isolation/over-reliance (e.g., >3 h/day for 7 days) | S |

## 5. Key User Flows

### 5.1 First-time user
```
Install → Welcome & AI disclosure → Age gate → Language & tone → Consent (itemised)
→ Goals → WHO-5 (+ optional PHQ-9/GAD-7) → [PHQ-9 item 9 > 0 ? → Risk flow]
→ Optional safety plan & emergency contact → Home → First conversation
```

### 5.2 Typical daily session
```
Notification/open → Mood tap → Chat ("What would help today?")
→ Intent: Listen / Skill / Learn → (Exercise via protocol engine) → Distress rating
→ Session summary + next step → Home
```

### 5.3 Crisis
```
Any message → Risk layer tier ≥3 → Scripted crisis response
→ Helplines shown + "Talk to a person now" → Warm handoff to counsellor
→ Safety plan surfaced → Follow-up check-in within 24 h → Clinical review of event
```

## 6. Non-Functional Requirements (NFR)

| ID | Category | Requirement |
|---|---|---|
| NFR-01 | Performance | p95 first-token latency < 2 s; risk classification < 300 ms |
| NFR-02 | Availability | 99.9% for chat; **99.95% for crisis resources** (helplines served from app bundle/offline) |
| NFR-03 | Scalability | 10k concurrent sessions at Phase 2 without degradation |
| NFR-04 | Security | TLS 1.3, AES-256 at rest, field-level encryption for conversation content |
| NFR-05 | Privacy | Data residency in India; zero-retention LLM contracts |
| NFR-06 | Accessibility | WCAG 2.1 AA; screen-reader support; adjustable font size; voice |
| NFR-07 | Device | Android 8+, 2 GB RAM, app size < 40 MB; works on 3G |
| NFR-08 | Localisation | All UI and clinical content professionally translated & clinically reviewed |
| NFR-09 | Auditability | Immutable audit log for data access and risk events |
| NFR-10 | Reading level | Responses at ≈ grade 6–8 reading level |

## 7. Content Requirements

- All psychoeducation and exercise content is **authored or reviewed by a licensed clinician**, versioned, with a review date (≤ 12 months).
- Cultural adaptation (examples, metaphors, family dynamics, faith-sensitive options).
- Crisis scripts are **fixed templates** approved by the Clinical Advisory Board.

## 8. Analytics & Success Metrics

| Category | Metric | MVP target |
|---|---|---|
| Activation | % installs completing onboarding | ≥ 60% |
| Engagement | D7 / D30 retention | ≥ 30% / ≥ 15% |
| Value | Avg distress reduction pre/post exercise | ≥ 2 points (0–10) |
| Outcome | PHQ-9 / GAD-7 change at 8 weeks | Reported; reliable-improvement rate tracked |
| Experience | "I felt heard" (post-session) | ≥ 80% yes |
| Safety | Crisis handoff connect time | p90 < 5 min |
| Safety | Unsafe-response reports confirmed by review | < 0.1% of sessions |

Analytics events must not contain message content; use de-identified event schemas (see TDD).

## 9. Release Plan

| Phase | Timeline (indicative) | Scope |
|---|---|---|
| **0. Discovery** | Month 0–1 | Research (MRD hypotheses), clinical board formed, crisis partner signed |
| **1. MVP / Closed beta** | Month 1–4 | E1, E2 (text), E3 (exercises), E4 (basic), E5, E8; EN + 2 languages; Android; 200–500 beta users under clinical monitoring |
| **2. Public launch + Personalisation** | Month 5–9 | Memory, voice, programmes, insights, therapist booking, iOS, premium tier |
| **3. Clinical & B2B** | Month 10–15 | Clinician portal, org dashboard, SSO, pilot outcome study |
| **4. Evidence & Scale** | Month 16+ | RCT, regulatory pathway (if therapeutic claims), new geographies |

### MVP exit criteria
- 0 unresolved critical safety findings from red-team.
- Risk classifier tier ≥3 recall ≥ 0.95 on held-out clinician-labelled set.
- Clinical board sign-off on all content & scripts.
- DPIA completed; penetration test passed.

## 10. Dependencies
LLM provider, ASR/TTS provider with Indic support, crisis partner, India cloud region, payment gateway (Phase 2), clinicians for content.

## 11. Open Questions
1. Exact launch languages?
2. In-house vs partner counsellors for crisis handoff?
3. Will premium include human sessions or keep them pay-per-use?
4. Adolescent programme timeline?
