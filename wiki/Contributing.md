# Contributing

## Workflow

1. Branch from `main`, named `<type>-<short-description>`: `feat-…`, `fix-…`, `docs-…`, `chore-…`.
2. Make the change with tests.
3. Run the checks locally:
   ```bash
   cd backend
   ruff check . && ruff format --check . && pytest -q
   ```
4. Open a pull request into `main`. CI runs lint, formatting and tests (including PostgreSQL) and posts the risk-evaluation report.

## Rules that protect users

- **Never** let the AI model write crisis replies. Tier ≥ 3 must use approved templates.
- **Never** let a detector lower a risk tier. New detectors plug into `RiskClassifier`; the assessor takes the maximum.
- **Fail safe**: a failing detector must produce tier 2, not tier 0.
- **Don't** put message content in logs, analytics, notifications or `risk_events`.
- **Don't** change crisis text, helplines or the risk word list without clinical sign-off — bump the template `version`.
- **Don't** tune the lexicon on evaluation data.
- New user data must be encrypted, exported by `/v1/privacy/export` and deleted by `/v1/privacy/delete-account` — add tests for all three.

## Schema changes

Edit `koyala/db/models.py`, generate a migration (see [[Database and Migrations]]), review it, and run the tests — they fail if models and migrations differ.

## Content changes

Crisis templates, helplines and exercises live in `backend/koyala/content/`. Content PRs need a clinical reviewer.
