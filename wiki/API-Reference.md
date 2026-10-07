# API Reference

Interactive docs: run the backend and open `/docs` (Swagger) or `/redoc`.

All `/v1` endpoints except the public ones need `Authorization: Bearer <access_token>`.

## Authentication

| Method | Path | Notes |
|---|---|---|
| POST | `/v1/auth/anonymous` | Create an anonymous account → `user_id`, `access_token` (15 min), `refresh_token` (30 days) |
| POST | `/v1/auth/refresh` | `{refresh_token}` → new pair; the old refresh token is consumed. Reusing one revokes that sign-in |
| POST | `/v1/auth/logout` | `{refresh_token}` → 204 |

## Public (no token)

| Method | Path | Notes |
|---|---|---|
| GET | `/healthz` | Liveness |
| GET | `/v1/safety/resources?lang=en` | Helpline directory |
| GET | `/v1/exercises?lang=en` | Exercise list |

## Chat

| Method | Path | Notes |
|---|---|---|
| POST | `/v1/sessions` | `{language}` → `session_id` |
| POST | `/v1/sessions/{id}/messages` | `{text}` → turn (`type`: `message` / `crisis` / `exercise_step` / `fallback`, `risk_tier`, `actions`) |
| POST | `/v1/sessions/{id}/exercise` | `{exercise_id}` → first step |

## Tracking

| Method | Path | Notes |
|---|---|---|
| POST / GET | `/v1/assessments` | PHQ-9, GAD-7, WHO-5. PHQ-9 item 9 > 0 returns a `follow_up` and raises risk |
| POST / GET | `/v1/mood` | Score 1–5, emotions, factors, note. Note is risk-screened |
| POST / GET | `/v1/journal` | `private: true` excludes from all processing |
| DELETE | `/v1/journal/{id}` | |
| GET / PUT | `/v1/safety/plan` | Stanley–Brown, seven sections |
| GET | `/v1/check-ins?pending=true` | Follow-up check-ins |
| POST | `/v1/check-ins/{id}/ack` | Mark acknowledged |

## Counsellor handoff

| Method | Path | Notes |
|---|---|---|
| POST | `/v1/escalations` | `{channel: chat\|callback, callback_number?, language}` |
| GET | `/v1/escalations/{id}` | Own requests only |
| POST | `/v1/escalations/{id}/cancel` | |
| POST | `/v1/partner/escalations/{id}/status` | **Partner only**, `X-Partner-Token` header; `{status: connected\|closed}` |

## Privacy

| Method | Path | Notes |
|---|---|---|
| GET | `/v1/privacy/export` | All the user's data as a JSON download |
| POST | `/v1/privacy/delete-account` | `{"confirm": "DELETE"}` → 204; erases everything immediately |

## Turn `actions`

The client renders these as buttons:

| `kind` | Fields | Meaning |
|---|---|---|
| `call` | `label`, `number` | Dial a helpline |
| `handoff` | `label` | Start `POST /v1/escalations` |
| `safety_plan` | `label` | Open the safety plan |
| `exercise` | `label`, `ref` | Start exercise `ref` |
| `exercises` | `label` | Show the exercise list |
