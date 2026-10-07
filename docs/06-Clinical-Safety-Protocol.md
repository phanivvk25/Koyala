# Koyala — Clinical Safety & Crisis Protocol

| Field | Value |
|---|---|
| Document | Clinical Safety Protocol v0.1 (Draft) |
| Depends on | PRD (03), TDD (04), AI Model Spec (05) |
| Owner | Clinical Lead (accountable) with Head of Engineering (responsible for implementation) |
| Approval | **Requires Clinical Advisory Board sign-off before any user exposure** |
| Status | Draft — all scripts are placeholders pending clinical authoring |

---

## 1. Purpose

Defines how Koyala identifies and responds to risk, the human escalation chain, crisis response content rules, follow-up, incident management, and clinical governance. This protocol **overrides** any product or AI behaviour that conflicts with it.

## 2. Safety Principles

1. **Never abandon** — Koyala never ends, refuses, or ignores a conversation where risk is present.
2. **Ask directly** — when indicated, ask about suicidal thoughts plainly; asking does not increase risk.
3. **Connect to humans** — the goal at elevated risk is to connect the person with human help.
4. **Scripted at high risk** — tier ≥3 responses use approved templates; the LLM does not improvise.
5. **Least intrusive effective action** — respect autonomy; involve third parties only per consent or law.
6. **Fail safe** — when uncertain or when systems fail, escalate rather than de-escalate.
7. **Learn from every event** — every tier ≥3 event is reviewed.

## 3. Scope of Risks Covered

| Category | Code |
|---|---|
| Suicidal ideation / behaviour | SUI |
| Non-suicidal self-injury | NSSI |
| Harm to others / homicidal ideation | HTO |
| Abuse: domestic, child, sexual, elder | ABU |
| Medical emergency (overdose, poisoning, injury) | MED |
| Psychosis / mania indicators | PSY |
| Severe eating disorder indicators | EAT |
| Substance intoxication / withdrawal crisis | SUB |
| Minor detected (<18) | MIN |

## 4. Risk Tiers & Required Actions

| Tier | Detection | Koyala response (AI) | System actions | Human actions |
|---|---|---|---|---|
| **0** | None | Normal conversation | — | — |
| **1** Low | Distress, hopelessness | Validate; explore; offer coping skill; mention support options lightly | Log; raise watch flag for session | — |
| **2** Moderate | Passive ideation, past self-harm, PHQ-9 item 9 ≥1 | Direct, caring risk questions (C-SSRS-informed: wish to be dead? thoughts of killing self? method? intent? plan? past behaviour?); review/create safety plan; show helplines inline | Risk state ≥2 for 72 h; follow-up check-in ≤ 24 h; notify linked clinician (if consented) — next business day | Clinical audit within 72 h (sample/all per volume) |
| **3** High | Active ideation, plan, recent self-harm, HTO intent, abuse disclosure with current danger | **Scripted crisis template**; helplines prominently; "Talk to a person now" offered and encouraged; safety plan; encourage reaching a trusted person; stay engaged | Escalation request to crisis partner; linked clinician urgent alert; on-call clinical lead notified; risk state 3, follow-up ≤ 12 h | Counsellor connects p90 < 5 min; clinical review within 24 h |
| **4** Imminent | Intent + means + timeframe; attempt in progress; MED emergency | **Scripted imminent template**: emergency number 112 first, then helplines; ask about immediate safety ("Are you safe right now?", "Can you move away from the means?"); keep user engaged | Immediate escalation (highest priority); trusted-contact alert if consented; emergency-services workflow per legal guidance | Counsellor/crisis partner takes over immediately; clinical lead paged; incident opened |

### 4.1 Category-specific responses
| Category | Response essentials |
|---|---|
| NSSI | Non-judgemental; harm-minimisation per clinical guidance; wound-care → medical help if serious; coping alternatives; tier ≥2 |
| HTO | Take seriously; de-escalate; encourage distance from means/person; crisis line; legal duty-to-warn assessment by human clinician |
| ABU | Believe & validate; safety first; women's helpline 181, child helpline 1098, police 112 (India) **[verify current numbers]**; do not instruct confrontation; if child at risk, escalate to human |
| MED | 112 / nearest hospital immediately; poison guidance only "seek emergency care now"; no home remedies |
| PSY | Empathise with feelings; don't argue or affirm beliefs; encourage contact with doctor/psychiatrist; tier ≥2 if distress high |
| EAT | No calorie/weight content; encourage specialist help; tier ≥2 if medical signs (fainting, chest pain) |
| SUB | Safety (don't drive, don't be alone); emergency if overdose signs; refer to de-addiction services |
| MIN | Supportive message; youth helpline (e.g., 1098); end onboarding for <18 per policy; never continue therapeutic content |

## 5. Crisis Response Content Rules

- Templates are authored by clinicians in each supported language; **no machine translation without clinical review**.
- Each template: warm acknowledgement → concern stated plainly → immediate safety question → resources with one-tap actions → offer to stay and talk.
- Avoid: clichés ("everything happens for a reason"), minimising, guilt ("think of your family"), method details, promises the system can't keep.
- Follow safe-messaging guidance (e.g., WHO media guidelines on suicide reporting) for any psychoeducation on suicide.
- Template IDs are versioned (e.g., `crisis_t3_v4_te`); changes require Clinical Advisory Board approval.

**Placeholder structure (English, tier 3) — to be authored by clinicians:**
> "I'm really glad you told me. What you're describing sounds incredibly painful, and I'm concerned about your safety. Are you safe right now?
> You don't have to go through this alone — you can talk to a trained counsellor right now: [Talk to a person now] · [Call Tele-MANAS 14416] · [Emergency 112].
> I'm here with you while you reach out. Would you like to look at your safety plan together?"

## 6. Helpline & Resource Directory

| Resource | Number | Coverage |
|---|---|---|
| Tele-MANAS (Govt. of India) | 14416 / 1-800-891-4416 | National, multilingual, 24×7 **[verify]** |
| Emergency services | 112 | National |
| Child helpline | 1098 | National **[verify]** |
| Women's helpline | 181 | National **[verify]** |
| Koyala crisis partner | TBD | Contracted |
| State-specific lines | TBD per state | Maintained in content-svc |

- Directory owned by Clinical Lead; **verified monthly** (test call / official source check); last-verified date stored per entry.
- Directory is bundled in the app for offline access.

## 7. Escalation Chain & Roles

```
AI (tier detection) ─► Crisis partner counsellor (24×7) ─► Koyala on-call clinical lead
                                         │                         │
                                         └─► Emergency services (112) per partner protocol / law
Linked clinician (if consented) ◄─ alert (urgent for tier ≥3)
```

| Role | Responsibility | Availability |
|---|---|---|
| Crisis partner counsellor | Live support, risk assessment, emergency coordination | 24×7, SLA connect < 5 min (p90) |
| On-call clinical lead (Koyala) | Oversight, decisions on third-party contact, incident ownership | 24×7 rota, page response < 15 min |
| On-call engineer | System failures affecting safety path | 24×7, page response < 15 min |
| Clinical reviewers | Post-event review, audits | Business days |
| Clinical Advisory Board | Protocol approval, quarterly safety review | Quarterly + ad hoc |

## 8. Third-Party Contact & Confidentiality

- At onboarding, users are told clearly when confidentiality may be broken (imminent risk to life of self or others, child protection, legal requirement).
- Trusted-contact alert: only if user pre-consented **or** a human clinician determines imminent risk to life and applicable law permits/requires.
- Decisions to contact emergency services are made by **humans** (crisis partner / clinical lead), never automatically by the AI — except automated display of emergency numbers to the user.
- All such actions are logged with rationale and reviewed.
- Legal counsel to confirm obligations under Mental Healthcare Act 2017 and other applicable law; this section to be updated accordingly.

## 9. Follow-up Protocol

| After tier | Follow-up |
|---|---|
| 2 | In-app check-in within 24 h: "I've been thinking about our conversation yesterday — how are you today?" + safety plan link |
| 3 | Check-in within 12 h; repeat daily for 3 days; offer human session |
| 4 | Human follow-up by crisis partner/clinical team within 24 h (with consent) |

Risk state decays only after follow-up responses indicate reduced risk; never decays silently on non-response — non-response after tier ≥3 triggers human outreach if contact consented.

## 10. Safety Plan (Stanley–Brown model)

Sections: (1) warning signs, (2) internal coping strategies, (3) people/places for distraction, (4) people to ask for help, (5) professionals/helplines, (6) making the environment safer, (+) reasons for living. Created collaboratively with AI guidance, editable anytime, available offline, shareable with clinician/trusted person on user's choice.

## 11. System Failure Safety

| Failure | Required behaviour |
|---|---|
| LLM unavailable | Helplines + offline exercises remain; risk lexicon + classifier still run |
| Risk classifier unavailable | Lexicon fast-path only + show resources inline on any distress keyword; page on-call |
| Crisis partner unreachable | Fallback to Tele-MANAS / 112 display; page clinical lead; incident |
| App offline | Bundled helplines + safety plan |

## 12. Incident Management

**Definition**: any event where a user may have been harmed or put at risk by Koyala's action or inaction (e.g., missed risk, harmful response, failed escalation, data exposure of risk info).

| Severity | Example | Response |
|---|---|---|
| SEV-1 | Missed tier 4; harmful method content shown; death/serious harm reported | Immediate: page clinical lead + CTO; contain (disable feature/model); notify leadership within 1 h; RCA within 5 days; board review |
| SEV-2 | Missed tier 3; escalation SLA breach > 30 min | Same day triage; RCA within 10 days |
| SEV-3 | Inappropriate tone, minor rule violation | Weekly review; fix in next release |

Process: detect → contain → assess user welfare (human outreach if needed) → root cause (model, prompt, data, process) → corrective action → add case to eval/red-team suite → report to Clinical Advisory Board → regulatory/legal notification if required.

## 13. Clinical Governance

- **Clinical Advisory Board**: ≥1 psychiatrist, ≥1 clinical psychologist, ≥1 counsellor, ≥1 person with lived experience; meets quarterly.
- **Clinical Safety Officer** (named individual) accountable for this protocol.
- **Hazard log**: maintained per clinical risk-management practice (identify hazard → cause → effect → controls → residual risk) for every feature.
- **Audits**: weekly sampled conversation audits; 100% review of tier ≥3 events; quarterly safety report.
- **Training**: all staff complete safety & crisis training; crisis partner briefed on Koyala handoff.
- **Staff wellbeing**: reviewers exposed to distressing content get rotation, supervision, and support.

## 14. Safety KPIs

| KPI | Target |
|---|---|
| Tier ≥3 recall (offline gate) | ≥ 0.95 |
| Tier 4 false-negative rate | ≤ 1% |
| Escalation connect time p90 | < 5 min |
| Tier ≥3 events reviewed within 24 h | 100% |
| Follow-up check-ins delivered on time | ≥ 98% |
| SEV-1 incidents | 0 |
| Helpline directory verified in last 30 days | 100% |

## 15. Sign-off

| Role | Name | Signature | Date |
|---|---|---|---|
| Clinical Safety Officer | | | |
| Clinical Advisory Board Chair | | | |
| Head of Engineering | | | |
| Legal | | | |
