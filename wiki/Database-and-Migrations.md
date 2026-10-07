# Database and Migrations

PostgreSQL 16 in production and CI; SQLite works for tests.

## Tables

| Table | Contents | Encrypted |
|---|---|---|
| `users` | Id, how the account was created, wrapped per-user data key | — |
| `chat_sessions` | Session metadata; active exercise state | exercise state |
| `messages` | Chat history | **content** |
| `risk_states` | Sticky risk floor, PHQ-9 floor, next follow-up time | — |
| `risk_events` | Audit of tier ≥ 2 turns: tier and categories only | — (no content) |
| `refresh_tokens` | SHA-256 hashes, families, expiry, use, revocation | hashed |
| `user_records` | Assessments, mood, journal, safety plan, check-ins | **payload** |
| `escalations` | Counsellor requests, status, SLA | **callback number** |

## Encryption

Each user has a random AES-256-GCM data key, stored wrapped by the master key. Encrypted values are bound to their user, so a row copied to another account won't decrypt. Code: `koyala/db/crypto.py`.

## Migrations

```bash
cd backend
python -m koyala.db.migrate                         # apply all (uses KOYALA_DATABASE_URL)
alembic revision --autogenerate -m "describe change" # after editing koyala/db/models.py
```

Always read the generated file before committing. A test fails if models and migrations ever differ, and every migration is tested downgrading and re-upgrading.

| Revision | Adds |
|---|---|
| 0001 | users, chat_sessions, messages, risk_states, risk_events |
| 0002 | refresh_tokens, users.auth_type |
| 0003 | user_records |
| 0004 | escalations |

## Local database

```bash
docker compose up -d db   # postgres:16, user/password koyala/koyala-dev-only, db koyala
```
