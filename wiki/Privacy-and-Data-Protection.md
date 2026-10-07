# Privacy and Data Protection

Governing document: [Privacy, Security & Compliance](https://github.com/phanivvk25/Koyala/blob/main/docs/07-Privacy-Security-Compliance.md) (DPDP Act 2023, Mental Healthcare Act 2017).

## What's built

| Control | How |
|---|---|
| Anonymous accounts | No name, phone or email needed to sign up |
| Encryption at rest | Messages, journal, mood, assessments, safety plan, exercise answers and callback numbers encrypted with a per-user key |
| Redaction before AI | Emails, phone numbers, links, Aadhaar- and PAN-like IDs replaced with placeholders before text reaches the AI model or risk judge |
| Private journal | `private: true` entries are never processed automatically |
| Minimum sharing with crisis partner | Risk tier, categories, language, channel, callback number — no messages, no user id |
| Content-free notifications | Push text never mentions risk or mental health |
| Data export | `GET /v1/privacy/export` — everything, decrypted, as JSON |
| Account deletion | `POST /v1/privacy/delete-account` — erased immediately; tokens stop working at once |
| No ads, no data sale | Business rule (BRD) |

## Not yet built / open

- Person and place names are **not** redacted (needs a name-detection model).
- Master key should move to a cloud key-management service.
- Backups keep deleted data until they roll off (≤ 35 days planned).
- **Legal question:** deletion currently removes the risk audit log, which TDD §12 proposed keeping for 7 years.
- Data-retention terms with the AI provider and DPDP cross-border transfer must be confirmed before real user data is sent.
- Privacy impact assessment (DPIA) not yet done.
