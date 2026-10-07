# Roadmap

## Done (backend MVP)

- Product documents (MRD, BRD, PRD, TDD, AI spec, safety protocol, compliance)
- Safety pipeline: risk tiers, crisis templates, output guard, fail-safe behaviour
- Exercises, PHQ-9 / GAD-7 / WHO-5
- Claude integration with redaction; optional LLM risk judge
- PostgreSQL with per-user encryption and migrations
- Anonymous accounts with rotating refresh tokens
- Mood, journal, assessments history, safety plan
- Counsellor handoff with paging and 5-minute SLA
- Follow-up check-ins
- Data export and account deletion
- Risk-detection evaluation harness

## Next — engineering

| Item | Why |
|---|---|
| Rate limits on sign-up and chat | Abuse and cost protection |
| Master key in cloud key management | Key safety |
| Dockerfile, deployment config for an India region | Go-live |
| Audit logging for data access | Compliance |
| Mobile app (React Native) | Users need a client |
| Daily repeat follow-ups for 3 days after tier ≥ 3 | Safety protocol §9 |
| Name / place redaction | Privacy |
| Phone or email sign-in | Account recovery |
| Multilingual UI and content | Hindi, Telugu at launch |

## Blocked on people / contracts

| Item | Owner |
|---|---|
| Clinical sign-off on crisis text, helplines, exercises, risk words | Clinical Advisory Board |
| Clinician-labelled risk set (~3,000 messages) | Clinical team |
| Crisis partner, paging service, push provider | Business |
| Wellness-vs-device opinion, DPIA, AI provider terms | Legal |
