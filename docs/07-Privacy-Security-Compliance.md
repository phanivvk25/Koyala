# Koyala — Privacy, Security & Regulatory Compliance

| Field | Value |
|---|---|
| Document | Compliance v0.1 (Draft) |
| Depends on | BRD (02), PRD (03), TDD (04), AI Model Spec (05), Safety Protocol (06) |
| Owner | Data Protection Officer / Legal, with Security Lead |
| Status | Draft — **not legal advice**; must be reviewed by qualified counsel in each jurisdiction |

---

## 1. Purpose

Sets out the legal, regulatory, privacy and security obligations applicable to Koyala and how the product meets them. Mental health data is among the most sensitive personal data; this document treats it accordingly.

## 2. Regulatory Landscape

### 2.1 India (launch market)
| Law / guideline | Relevance | Key obligations for Koyala |
|---|---|---|
| **Digital Personal Data Protection Act, 2023 (DPDP)** and Rules | All personal data | Notice & specific consent; purpose limitation; data minimisation; accuracy; security safeguards; breach notification to Data Protection Board & users; rights (access, correction, erasure, grievance, nominate); children's data (verifiable parental consent, no tracking/targeting); obligations scale if notified as Significant Data Fiduciary |
| **Mental Healthcare Act, 2017** | Rights of persons with mental illness | Right to confidentiality (s.23); restrictions on releasing information; dignity; applies strongly when human mental health professionals provide care |
| **IT Act, 2000 & SPDI Rules, 2011** | Sensitive personal data incl. health | Reasonable security practices (e.g., ISO 27001-aligned); transition to DPDP **[verify status]** |
| **Telemedicine Practice Guidelines, 2020** | Human practitioner consultations | Registered practitioner, consent, documentation; AI may not counsel/prescribe as a practitioner |
| **Medical Devices Rules, 2017 (CDSCO)** | Software making diagnostic/therapeutic claims | Wellness positioning avoids device classification; therapeutic claims → regulatory pathway **[verify current SaMD guidance]** |
| **Consumer Protection Act, 2019** & ASCI guidelines | Marketing claims | No misleading health claims |
| **CERT-In Directions (2022)** | Cyber incidents | Report specified incidents within 6 hours; log retention requirements **[verify]** |

### 2.2 Future markets (readiness)
| Jurisdiction | Instruments | Notes |
|---|---|---|
| USA | HIPAA (when acting for covered entities/B2B), FTC Act & Health Breach Notification Rule, state laws (e.g., Washington My Health My Data), FDA SaMD / digital health policies | Wellness vs. device line; BAAs with providers |
| EU / UK | GDPR / UK GDPR (Art. 9 special category data), EU AI Act, EU MDR / UK MDR | DPIA mandatory; AI Act obligations for high-risk systems if a medical device; transparency obligations for chatbots |
| Global | ISO 27001, ISO 27701, IEC 62304 / ISO 14971 (if device), SOC 2 | Certifications as B2B trust signals |

## 3. Data Inventory & Classification

| Data | Examples | Class | Lawful basis (India) |
|---|---|---|---|
| Identity | Phone, email, name | Confidential | Consent |
| Device/technical | Device ID, app version, IP (hashed) | Internal | Consent / legitimate use for security |
| Conversation content | Messages, audio | **Highly sensitive** | Consent (core service) |
| Assessments & mood | PHQ-9, GAD-7, mood logs | **Highly sensitive** | Consent |
| Risk events | Tier, actions | **Highly sensitive** | Consent + legitimate uses (medical emergency, threat to life) |
| Safety plan, journal | Free text | **Highly sensitive** | Consent |
| Clinician data | Name, registration no. | Confidential | Contract |
| Payment | Tokenised by gateway | Confidential | Contract |
| Analytics | De-identified events | Internal | Consent (analytics, separately toggleable) |
| Research data | De-identified transcripts | **Highly sensitive** | Separate explicit research consent + ethics approval |

## 4. Privacy by Design Controls

| Principle | Control |
|---|---|
| Minimisation | Anonymous mode; no contacts/location harvesting; state-level location only for helplines |
| Purpose limitation | Purpose-tagged consents; services check consent before processing (consent-svc) |
| Granular consent | Separate toggles: core, AI memory, analytics, research, clinician sharing, trusted contact |
| Transparency | Layered privacy notice in all supported languages; in-app "How Koyala uses your data" |
| User control | View/export/delete; per-entry private journal; memory viewer/editor |
| Separation | Identity DB separate from content DB; pseudonymous IDs in analytics |
| No secondary exploitation | No ads, no data sale, no individual data to employers/universities |
| Retention limits | Per TDD §12; automated deletion jobs |
| Children | <18 blocked at MVP; future youth programme requires verifiable parental consent and no behavioural tracking |

## 5. Consent Model

- Consent requests are **specific, informed, unambiguous, itemised** and recorded with version, timestamp, and channel.
- Withdrawal is as easy as granting (one toggle) and takes effect immediately in processing.
- Consent notice available in English + every supported Indian language.
- Re-consent required when purposes materially change.
- Consent manager integration (DPDP consent managers) evaluated for Phase 3.

## 6. Data Subject / Data Principal Rights

| Right | Implementation | SLA |
|---|---|---|
| Access / summary of processing | In-app export (JSON + readable PDF) | Instant / ≤ 7 days for full |
| Correction | Edit profile, memory items, safety plan | Instant |
| Erasure | In-app delete account | Hard delete ≤ 30 days; backups ≤ 35 days |
| Grievance redressal | In-app + email to Grievance Officer | Acknowledge 48 h; resolve ≤ 30 days **[verify DPDP Rules timeline]** |
| Nomination (DPDP) | Nominee field in settings | — |

## 7. Third Parties & Cross-Border Transfer

| Vendor | Data shared | Safeguards |
|---|---|---|
| LLM provider | Redacted conversation context | Zero data retention; no training on data; DPA; prefer in-region processing; transfer only to permitted countries under DPDP |
| ASR/TTS provider | Audio / text | Same as above; audio deleted after processing |
| Crisis partner | Minimum necessary risk context, with consent | Data-sharing agreement, confidentiality, security requirements |
| Cloud provider | All (encrypted) | India region; contractual security commitments |
| SMS/OTP, push | Phone number / device token only | DPA; no message content in notifications |
| Payment gateway | Billing details (tokenised) | PCI-DSS compliant gateway |

Vendor onboarding requires: security questionnaire, DPA, sub-processor list, breach-notification clause, right to audit.

## 8. Information Security Programme

### 8.1 Governance
- Security Lead and DPO appointed; Information Security Policy; annual risk assessment.
- Target ISO 27001 + ISO 27701 certification by Phase 3; SOC 2 Type II for international B2B.

### 8.2 Technical controls (summary; detail in TDD §9)
- Encryption in transit (TLS 1.3) and at rest (AES-256); envelope encryption per user for sensitive fields.
- KMS-managed keys, rotation, separation of duties for key admins.
- RBAC/ABAC, MFA for all staff, least privilege, quarterly access reviews.
- No production data in dev/staging; synthetic data only.
- Audited break-glass access to content (requires reason + second approver; user-visible access log in later phase).
- Secure SDLC: threat modelling per feature, SAST/DAST, dependency & container scanning, code review.
- Annual penetration testing + pre-launch pen test; mobile app security testing (OWASP MASVS).
- Logging & monitoring with SIEM; no sensitive content in logs.
- Backups encrypted, tested restores quarterly.
- Endpoint security & device management for staff.

### 8.3 AI-specific security
- Prompt-injection defences (TDD §9); model outputs never trigger privileged actions.
- Training data provenance tracking; poisoning checks on any user-derived data.
- Model access controls; prompt registry change approvals.
- Membership-inference/privacy testing before training on any user-derived data.

## 9. Breach & Incident Response

1. Detect & triage (security on-call) → 2. Contain → 3. Assess scope & sensitivity →
4. Notify: CERT-In (within 6 h for reportable incidents **[verify]**), Data Protection Board of India and affected users (per DPDP Rules timelines **[verify]**); B2B customers per contract →
5. Remediate & root cause → 6. Post-incident review & lessons learned.

Annual tabletop exercise including a "breach of mental health conversation data" scenario.

## 10. Data Protection Impact Assessment (DPIA)

A DPIA is mandatory **before MVP launch** and on any material change. Template sections:
1. Description of processing & purposes
2. Necessity & proportionality
3. Data flows (link to TDD diagrams)
4. Risks to individuals (re-identification, stigma, discrimination by employer, emotional harm from AI, breach)
5. Mitigations & residual risk
6. DPO opinion and sign-off
7. Review date

## 11. AI Transparency & Ethics

- Clear disclosure that users are interacting with AI (onboarding, chat header, on request).
- Published **model card** and plain-language "How Koyala's AI works and its limits".
- No automated decisions with legal or similarly significant effects; deterioration predictions only trigger human outreach.
- Fairness evaluation across languages, gender, region (AI Model Spec §9).
- Ethics committee review for any research or outcome study; registered trial for efficacy claims.
- Marketing review: no claims of diagnosis, cure, or treatment unless supported and permitted.

## 12. Regulatory Strategy (staged)

| Stage | Positioning | Regulatory actions |
|---|---|---|
| Phase 1–2 | General wellness & self-help support | Legal opinion confirming non-device status; claims review; DPDP compliance |
| Phase 3 | Clinician-support tools (notes, dashboards) | Review whether features constitute clinical decision support/SaMD; QMS groundwork (ISO 13485-aligned) |
| Phase 4 | Digital therapeutic claims (e.g., anxiety programme) | Clinical trial; CDSCO pathway; FDA/EU MDR if expanding; IEC 62304, ISO 14971 risk management |

## 13. Compliance Checklist (pre-launch)

- [ ] Legal opinion on product classification (wellness vs device)
- [ ] Privacy notice & consent texts (all languages) reviewed by counsel
- [ ] DPIA completed and signed
- [ ] DPAs signed with all processors; zero-retention confirmed with AI vendors
- [ ] Data residency verified (India region)
- [ ] Grievance Officer / DPO contact published
- [ ] Pen test passed; critical/high findings fixed
- [ ] Breach response plan & CERT-In contact process tested
- [ ] Crisis partner data-sharing agreement signed
- [ ] Clinical Safety Protocol signed off (doc 06)
- [ ] Marketing claims reviewed
- [ ] Age-gate & minors policy implemented
- [ ] Retention & deletion jobs tested end-to-end

## 14. Responsibilities (RACI)

| Activity | DPO/Legal | Security | Engineering | Clinical | Product |
|---|---|---|---|---|---|
| Consent & notices | A/R | C | R | C | C |
| DPIA | A | R | C | C | C |
| Security controls | C | A | R | I | I |
| Vendor DPAs | A/R | C | C | I | I |
| Breach response | A | R | R | C (user welfare) | I |
| Claims review | A | I | I | R | R |
| Regulatory pathway | A | I | C | R | C |

A = Accountable, R = Responsible, C = Consulted, I = Informed
