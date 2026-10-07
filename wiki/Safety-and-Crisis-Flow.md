# Safety and Crisis Flow

Governing document: [Clinical Safety & Crisis Protocol](https://github.com/phanivvk25/Koyala/blob/main/docs/06-Clinical-Safety-Protocol.md). This page explains how the code implements it.

> ⚠️ All crisis wording, helpline numbers and the risk word list are **placeholders** until the Clinical Advisory Board signs them off.

## Risk tiers

| Tier | Meaning | What Koyala does |
|---|---|---|
| 0 | No risk | Normal conversation |
| 1 | Distress, hopelessness | Normal conversation; logged |
| 2 | Passive wish to be dead, past self-harm | AI gently asks directly about suicidal thoughts; helplines shown; follow-up in 24 h |
| 3 | Active ideation, plan, self-harm, harm to others, abuse | Fixed crisis message, helplines, "Talk to a counsellor now"; AI not called; follow-up in 12 h |
| 4 | Imminent danger, attempt in progress | Fixed crisis message leading with emergency 112; AI not called; on-call paged critical if handoff requested |

## Where risk is checked

- Every chat message.
- Mood notes and **non-private** journal entries (private entries are never processed).
- PHQ-9 question 9 answered above 0 → risk floored at tier 2 for 14 days.

## Risk stays raised

After tier 3, later messages are treated as at least tier 2 for 72 hours (tier 4 → at least tier 3).

## Counsellor handoff

`POST /v1/escalations`

1. Request saved, then handed to the crisis partner with **only**: risk tier, categories, language, channel, and callback number for call-backs. No messages, no user id.
2. On-call is paged (`high`, or `critical` at tier 4).
3. Helplines are returned with every response, whatever happens.
4. Partner unavailable → status `failed`, user told to call a helpline, on-call paged.
5. Not connected within 5 minutes → on-call paged once (`sweep-escalations` job).
6. Repeated taps return the open request — no duplicates.

The partner reports progress via `POST /v1/partner/escalations/{id}/status` with `X-Partner-Token`.

## Follow-up check-ins

24 h after tier 2, 12 h after tier ≥ 3: an in-app check-in plus a push notification whose text never mentions risk. A tier ≥ 3 check-in unanswered for 24 h pages on-call once. See [[Background Jobs]].

## Placeholders to replace before launch

| Placeholder | Replace with |
|---|---|
| `content/crisis_templates.yaml` | Clinician-authored, translated crisis and follow-up messages |
| `content/resources.yaml` | Verified helpline directory (monthly re-check) |
| `safety/lexicon.py` | Clinician- and linguist-reviewed risk phrases |
| `StubPartner` | Contracted crisis partner API |
| `LogPager` | On-call paging service |
| `LogNotifier` | FCM / APNs push |
