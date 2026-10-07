# Configuration

All settings are environment variables. See `backend/.env.example`.

| Variable | Default | Purpose |
|---|---|---|
| `KOYALA_DATABASE_URL` | *(unset → in-memory)* | e.g. `postgresql+psycopg://user:pass@host/koyala` |
| `KOYALA_MASTER_KEY` | — | **Required with a database.** Base64 32-byte key that wraps each user's data key |
| `KOYALA_JWT_SECRET` | random per process | **Required with a database.** ≥ 32 bytes |
| `KOYALA_LLM_PROVIDER` | `stub` | `stub` (offline) or `anthropic` |
| `KOYALA_LLM_MODEL` | `claude-opus-5-5` | Reply model |
| `KOYALA_LLM_EFFORT` | `medium` | `low` / `medium` / `high` |
| `KOYALA_RISK_JUDGE` | `off` | `anthropic` enables the LLM risk judge |
| `KOYALA_RISK_JUDGE_MODEL` | `claude-opus-5-5` | Judge model |
| `ANTHROPIC_API_KEY` | — | Needed when either of the above uses `anthropic` |
| `KOYALA_PARTNER_TOKEN` | — | Shared secret the crisis partner sends as `X-Partner-Token`. Unset → partner callbacks return 503 |
| `KOYALA_TEST_DATABASE_URL` | — | Tests only. **The suite wipes this database** |

## Generating secrets

```bash
python -c "from koyala.db.crypto import Crypto; print(Crypto.generate_key())"   # KOYALA_MASTER_KEY
python -c "import secrets; print(secrets.token_urlsafe(48))"                    # KOYALA_JWT_SECRET
```

## Production notes

- Keep the master key in a cloud key-management service, not an environment file. Losing it makes all stored content unreadable.
- Before sending real user data to a model provider, confirm data-retention terms and DPDP cross-border rules ([Compliance §7](https://github.com/phanivvk25/Koyala/blob/main/docs/07-Privacy-Security-Compliance.md)).
- The LLM judge adds one model call per non-crisis message — measure latency and cost first.
