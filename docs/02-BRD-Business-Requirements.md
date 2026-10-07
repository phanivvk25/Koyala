# Koyala — Business Requirements Document (BRD)

| Field | Value |
|---|---|
| Document | BRD v0.1 (Draft) |
| Depends on | MRD (01) |
| Feeds into | PRD (03) |
| Status | Draft for review |

---

## 1. Purpose

Defines **why the business is building Koyala**, the **business objectives**, **revenue model**, **stakeholders**, **constraints** and **business-level requirements**. Product features are specified in the PRD.

## 2. Business Objectives

| ID | Objective | Measure | Target (indicative, 24 months) |
|---|---|---|---|
| BO-1 | Reach users who lack access to care | Monthly active users (MAU) | 100k MAU |
| BO-2 | Demonstrate clinical value | % users with ≥5-pt PHQ-9 reduction after 8 weeks (among those starting ≥10) | ≥40% |
| BO-3 | Maintain safety | Critical safety incidents attributable to the AI | 0 |
| BO-4 | Build sustainable revenue | Annual recurring revenue (ARR) | Set by finance plan |
| BO-5 | Win institutional customers | Paid B2B contracts | 20+ |
| BO-6 | Earn trust | App store rating / "felt safe" score | ≥4.5 / ≥85% |

> Targets are placeholders to be finalised with the finance model and pilot data.

## 3. Scope

### In scope
- Consumer mobile app (Android first, then iOS) and web.
- AI conversational companion with self-help programmes.
- Crisis detection and escalation to helplines / partner counsellors.
- Clinician portal (Phase 3) and organisation admin dashboard (Phase 3).

### Out of scope (initial)
- Diagnosis, prescribing, or medication management.
- Treatment of severe mental illness (psychosis, bipolar mania, severe eating disorders) — users are referred out.
- Users under 18 (until a dedicated adolescent programme with guardian consent is designed).
- Insurance billing integrations.

## 4. Stakeholders

| Stakeholder | Interest | Involvement |
|---|---|---|
| Founders / leadership | Vision, funding, risk | Approve BRD/PRD |
| Clinical Advisory Board (psychiatrist, clinical psychologist, counsellor) | Safety & efficacy | Approves protocols, crisis scripts, content |
| Product & Design | Usability | Owns PRD, UX |
| Engineering & AI/ML | Feasibility | Owns TDD, AI spec |
| Legal / Compliance / DPO | Law & privacy | Owns compliance doc, consent texts |
| End users | Help, privacy | Research participants, beta |
| B2B buyers (HR, universities) | ROI, duty of care | Pilots |
| Crisis partner (helpline / counsellor network) | Clear handoff | SLA agreement |
| Investors | Growth, defensibility | Reporting |

## 5. Business Model

### 5.1 Revenue streams

| Stream | Model | Notes |
|---|---|---|
| **B2C Freemium** | Free core (chat, mood, crisis, basic exercises). Premium subscription for full programmes, voice, insights, long-term memory | Crisis & safety features are **always free** — never paywalled |
| **B2C Human sessions** | Pay-per-session with partner therapists (commission) | Phase 2–3 |
| **B2B Employers** | Per-employee-per-month (PEPM) | Aggregate-only reporting |
| **B2B Universities** | Annual licence per student band | Includes counselling-centre triage |
| **B2B2C Clinicians** | Per-clinician seat for portal | Free tier to seed adoption |
| **Grants / public health** | Programme contracts | Language expansion, underserved regions |

### 5.2 Explicit non-revenue policies
- **No advertising**, ever.
- **No sale or sharing of personal data** for marketing.
- **No individual-level data to employers/universities.**

## 6. Business Requirements

| ID | Requirement | Priority |
|---|---|---|
| BR-01 | The product shall be positioned and marketed as a **wellness & support tool**, not a diagnostic or treatment device, until clinical evidence and regulatory clearance exist | M |
| BR-02 | Safety and crisis features shall be available to all users free of charge | M |
| BR-03 | The business shall maintain a Clinical Advisory Board with sign-off authority over clinical content and safety protocols | M |
| BR-04 | The business shall have a contracted 24×7 human escalation path (in-house or partner) before public launch | M |
| BR-05 | Personal data shall be stored in India for Indian users and processed under DPDP Act 2023 | M |
| BR-06 | AI model vendors shall be contracted with zero-data-retention and no-training-on-customer-data terms | M |
| BR-07 | B2B reporting shall only expose aggregated, k-anonymised data (minimum group size k ≥ 10) | M |
| BR-08 | The business shall run a pilot outcome study with an ethics committee before making efficacy claims | S |
| BR-09 | The platform shall support subscription billing via Indian payment rails (UPI, cards) and app stores | S |
| BR-10 | The platform shall support white-labelling for B2B customers | C |

## 7. Key Business Processes

1. **User acquisition → onboarding → engagement → (optional) upgrade → (optional) human care referral**
2. **B2B sales → pilot → contract → onboarding (SSO/codes) → quarterly aggregate reporting → renewal**
3. **Safety incident → triage → clinical review → root-cause → model/protocol update → board report**
4. **Content lifecycle → clinician authoring → review → publish → periodic re-review (every 12 months)**

## 8. Constraints

- **Regulatory**: DPDP Act 2023, Mental Healthcare Act 2017 (rights of persons with mental illness, confidentiality), IT Act 2000 & rules, Telemedicine Practice Guidelines 2020 (when human practitioners consult), CDSCO medical-device rules if clinical claims are made. Later: HIPAA, GDPR, EU AI Act.
- **Budget**: MVP must be achievable with a small team (≈ 6–10 people) — see PRD release plan.
- **Ethical**: Must not exploit vulnerable users through engagement-maximising dark patterns.
- **Technical**: Must work on low-end Android devices and intermittent connectivity.

## 9. Assumptions & Dependencies

| Type | Item |
|---|---|
| Assumption | Users will accept AI support if transparently disclosed |
| Assumption | Clinical advisors are available at reasonable cost |
| Dependency | Third-party LLM provider with acceptable privacy terms and Indic-language quality |
| Dependency | Crisis partner agreement (helpline/counsellor network) |
| Dependency | Cloud region in India for data residency |

## 10. Business Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Safety incident / suicide of a user | Low–Med | Critical | Clinical Safety Protocol (06), insurance, incident process |
| Regulatory reclassification as medical device | Med | High | Careful claims, regulatory counsel, evidence plan |
| LLM vendor cost spikes | Med | Med | Model abstraction layer, smaller models for routine turns |
| Low B2C monetisation | High | Med | B2B-led revenue |
| Data breach | Low | Critical | Security programme (07), cyber insurance |

## 11. Cost Drivers (for finance model)

- LLM inference (per conversation turn), speech APIs.
- Clinical staff / advisory board, crisis partner fees.
- Cloud hosting (India region), security audits, legal/compliance.
- Content creation & translation by clinicians.
- Clinical study costs.

## 12. Approval

| Role | Name | Decision | Date |
|---|---|---|---|
| CEO / Founder | | | |
| Clinical Lead | | | |
| Legal / DPO | | | |
