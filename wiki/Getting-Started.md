# Getting Started

## Prerequisites

- Python 3.11+
- Docker (optional, for PostgreSQL)

## 1. Run with in-memory storage (quickest)

```bash
git clone https://github.com/phanivvk25/Koyala.git
cd Koyala/backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]" uvicorn
pytest -q                          # all tests should pass
uvicorn koyala.main:app --reload   # http://localhost:8000/docs
```

Data is lost on restart and the AI model is an offline stub. Good for exploring the API.

## 2. Try it

Open `http://localhost:8000/docs` (interactive API), or:

```bash
TOKEN=$(curl -s -X POST localhost:8000/v1/auth/anonymous | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
SID=$(curl -s -X POST localhost:8000/v1/sessions -H "Authorization: Bearer $TOKEN" \
      -H 'content-type: application/json' -d '{}' | python -c "import sys,json;print(json.load(sys.stdin)['session_id'])")
curl -s -X POST localhost:8000/v1/sessions/$SID/messages -H "Authorization: Bearer $TOKEN" \
     -H 'content-type: application/json' -d '{"text":"Work has been really stressful"}'
```

## 3. Run with PostgreSQL

```bash
docker compose up -d db                      # from the repo root
cd backend
cp .env.example .env
# fill in KOYALA_MASTER_KEY and KOYALA_JWT_SECRET (commands are in .env.example)
set -a && . ./.env && set +a
python -m koyala.db.migrate                  # create tables
uvicorn koyala.main:app --reload
```

## 4. Use Claude as the model (optional)

```bash
export KOYALA_LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=...
```

See [[Configuration]] for every setting.

## Running tests against PostgreSQL

```bash
KOYALA_TEST_DATABASE_URL=postgresql+psycopg://koyala:koyala-dev-only@localhost:5432/koyala pytest -q
```

⚠️ The test suite **drops and recreates the `public` schema** of that database. Use a throwaway database.
