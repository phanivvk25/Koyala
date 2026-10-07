# Koyala — Market Requirements Document (MRD)

| Field | Value |
|---|---|
| Document | MRD v0.1 (Draft) |
| Product | Koyala — AI-assisted mental health companion |
| Owner | Product / Founders |
| Status | Draft for review |
| Next documents | BRD (02), PRD (03) |

> **Note on figures:** Market statistics below are drawn from commonly cited public sources (WHO, India National Mental Health Survey 2015–16, etc.). Every figure marked **[verify]** must be re-checked against the latest primary source before external use (investor decks, regulatory filings).

---

## 1. Purpose

This document defines the **market problem**, **target segments**, **competitive landscape**, and the **market-level requirements** a mental health AI product must satisfy to succeed. It answers *"Is there a real, reachable market need, and what must we offer to win it?"* It intentionally avoids feature design (see PRD) and technical design (see TDD).

## 2. Problem Statement

1. **High prevalence** — WHO estimates roughly 1 in 8 people globally live with a mental disorder; anxiety and depression are the most common **[verify]**.
2. **Huge treatment gap** — India's National Mental Health Survey (2015–16) reported ~10–11% adult prevalence of mental disorders and a treatment gap of roughly 70–90% depending on the condition **[verify]**.
3. **Workforce shortage** — India has well under 1 psychiatrist per 100,000 people and a similarly small pool of clinical psychologists **[verify]**; access outside metros is very limited.
4. **Stigma** — many people will not visit a clinic, but will type into a phone privately at 2 a.m.
5. **Cost** — private therapy sessions are unaffordable for most students and early-career workers.
6. **Language & culture** — most digital tools are English-first and Western-framed; distress is often expressed somatically or in code-mixed language (e.g., Hinglish, Tenglish).
7. **Continuity gap** — even people in therapy have 1 hour/week of contact; the other 167 hours are unsupported.

## 3. Market Opportunity

### 3.1 Segments

| Segment | Description | Need | Willingness to pay |
|---|---|---|---|
| **S1. Young adults / students (18–30)** | Exam stress, loneliness, relationships, career anxiety | Private, low-cost, always-on support | Low (freemium) |
| **S2. Working professionals** | Burnout, anxiety, sleep | Quick tools, confidentiality from employer | Medium |
| **S3. Employers (B2B EAP)** | HR wanting wellbeing benefits | Engagement, aggregate reporting, compliance | High |
| **S4. Universities** | Student counselling centres overwhelmed | Triage, after-hours cover, referral | Medium–High |
| **S5. Clinicians / clinics** | Therapists, psychiatrists | Between-session support, notes, outcomes tracking | Medium–High |
| **S6. Insurers / payers** | Mental health cover now increasingly mandated | Cost reduction, measurable outcomes | High (later stage) |
| **S7. Public health / NGOs** | Government programmes, helplines | Scale, local languages, low cost | Grant / contract |

### 3.2 Sizing approach (to be completed with real data)

- **TAM**: All adults in target geographies with mild–moderate mental health needs.
- **SAM**: Smartphone users, 18+, in launch languages, in launch geography (India first).
- **SOM**: Realistic 3-year reach via B2C organic + 10–30 B2B contracts.

> Action: Finance to populate with sourced numbers; do not publish estimates without citations.

## 4. Target Customer & User Insights (hypotheses to validate)

| # | Hypothesis | Validation method |
|---|---|---|
| H1 | Users prefer starting with an anonymous AI before a human | Survey + landing-page test |
| H2 | Users in tier-2/3 cities want native-language support | Interviews (n≥30) |
| H3 | Employers will pay per-employee-per-month for a solution with aggregate (not individual) reporting | 10 HR discovery calls |
| H4 | Therapists will recommend a tool that reports homework adherence and PHQ-9/GAD-7 trends | 15 clinician interviews |
| H5 | Trust depends more on safety & privacy than on "smartness" | Concept testing |

## 5. Competitive Landscape

| Competitor (type) | Strengths | Gaps / opportunities for Koyala |
|---|---|---|
| **Wysa** (AI chatbot + human coaches; India-origin) | Clinical evidence programme, B2B traction, regulatory progress **[verify]** | Limited deep Indic-language & code-mixed support **[verify]** |
| **Amaha (formerly InnerHour)** (India; self-help + therapists + psychiatry) | Full care continuum | AI conversation less central |
| **YourDOST** (India; online counselling) | Large counsellor network, B2B | Human-capacity bound, less AI |
| **Woebot-style CBT bots** (US) | Strong CBT fidelity research | Market changes / consumer availability uncertain **[verify]**; not India-localised |
| **Headspace / Calm** (meditation) | Brand, content quality | Not conversational therapy; Western framing |
| **General-purpose AI chatbots** | Very capable conversation, free | Not designed for clinical safety, no crisis protocol, no measurement-based care, privacy concerns |
| **Tele-MANAS (Govt. of India helpline)** | Free, national, multilingual human support | Not a self-help companion; Koyala should **refer to**, not compete with it |

### 5.1 Positioning statement

> For **people in India (and later other emerging markets) experiencing everyday stress, anxiety and low mood**, **Koyala** is an **AI mental health companion** that offers **safe, private, evidence-based support in their own language, any time**, and **connects them to human care when needed**. Unlike general chatbots, Koyala is **built clinical-safety-first** with crisis detection, validated assessments and clinician oversight.

### 5.2 Differentiators (must be true to win)

1. **Safety-first** — visible crisis protocol, clinician-approved content.
2. **Indic & code-mixed language fluency** + culturally adapted content.
3. **Evidence-based** — CBT/DBT/ACT protocols, measurement-based care (PHQ-9, GAD-7).
4. **Bridge to humans** — stepped care into therapists and helplines.
5. **Privacy by design** — anonymous mode, no ad monetisation, in-country data storage.

## 6. Market Requirements

Priority: **M** = Must, **S** = Should, **C** = Could.

| ID | Requirement | Priority | Rationale |
|---|---|---|---|
| MR-01 | Provide 24×7 conversational emotional support | M | Core unmet need (after-hours, stigma) |
| MR-02 | Detect crisis and connect to human help / helplines | M | Ethical + legal necessity; trust |
| MR-03 | Support at least English + 2 Indian languages at launch, incl. code-mixed input | M | Differentiation, reach |
| MR-04 | Offer evidence-based self-help exercises | M | Efficacy, clinician endorsement |
| MR-05 | Track mood and validated outcome scores | M | Demonstrate value to users, B2B, payers |
| MR-06 | Anonymous / low-identity usage option | M | Stigma |
| MR-07 | Comply with DPDP Act 2023 and Mental Healthcare Act 2017 | M | Legal |
| MR-08 | Free tier usable on low-end Android & low bandwidth | M | Mass-market reach |
| MR-09 | Pathway to licensed human therapists | S | Stepped care, revenue |
| MR-10 | Employer/university dashboard with **aggregate-only** analytics | S | B2B revenue |
| MR-11 | Clinician portal (homework, outcomes, notes) | S | B2B2C channel |
| MR-12 | Voice interaction | S | Literacy, accessibility |
| MR-13 | Wearable integration | C | Differentiated insights |
| MR-14 | Expansion to other geographies (HIPAA/GDPR readiness) | C | Growth |

## 7. Go-to-Market Channels (initial view)

1. **B2C organic** — content in Indian languages (Instagram, YouTube, Sharechat), SEO for "anxiety help in Telugu/Hindi".
2. **Universities** — pilot with 2–3 colleges' counselling cells.
3. **Employers** — HR/EAP partnerships, start with startups/IT services.
4. **Clinicians** — free clinician portal to seed B2B2C referrals.
5. **NGO / public health** — partnerships for referral and language content.

## 8. Market Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Users distrust AI for mental health | Low adoption | Transparency, clinician endorsement, safety messaging |
| Well-funded incumbents | Price pressure | Language & culture niche, B2B focus |
| A safety incident damages brand | Severe | See Clinical Safety Protocol (doc 06) |
| Regulatory tightening on AI in health | Delays | Wellness positioning first; regulatory roadmap (doc 07) |
| Low free→paid conversion in India | Revenue | B2B-led model (see BRD) |

## 9. Success Criteria for Market Validation (pre-build)

- ≥30 user interviews + ≥300 survey responses supporting H1–H5.
- ≥3 signed LOIs from universities/employers for a pilot.
- ≥5 clinicians agreeing to be advisors / pilot users.

## 10. Open Questions

1. Launch languages: which two Indian languages first (e.g., Hindi + Telugu)?
2. B2C-first or B2B-first launch?
3. Will Koyala employ its own counsellors or partner for human escalation?
