# Demo and Deploy

## Local API

```powershell
cd C:\Users\shris\OneDrive\Documents\AI_Agents
python -m pip install -e ".[dev,ui]"
uvicorn main:app --reload --port 8000
```

Health:

```powershell
curl http://localhost:8000/health
```

Run a scenario:

```powershell
curl -X POST http://localhost:8000/api/v1/demo/scenarios/clean_em_837p/run
```

## Local UI

In another terminal:

```powershell
$env:AI_AGENTS_API_URL = "http://localhost:8000"
streamlit run streamlit_app.py
```

Demo scenarios:

- `clean_em_837p` -> `AUTO_PAY`
- `ncci_violation_837p` -> `DENY`
- `ncci_allowed_modifier_837p` -> `AUTO_PAY`
- `oig_excluded_837p` -> `DENY_AND_REPORT`
- `medical_necessity_failure_837p` -> `ESCALATE_SIU`

## Reference DB

For the full CMS NCCI reference DB, set:

```powershell
$env:AI_AGENTS_REFERENCE_DB = "C:\Users\shris\OneDrive\Documents\AI_Agents\.demo\claims_reference.db"
```

If unset or missing, the API creates a small seeded demo DB.

## Docker

```powershell
docker build -f Dockerfile.api -t ai-agents-claims-api .
docker run -p 8000:8000 -e PORT=8000 ai-agents-claims-api
```

For full NCCI lookups in Docker, mount the DB:

```powershell
docker run -p 8000:8000 `
  -e PORT=8000 `
  -e AI_AGENTS_REFERENCE_DB=/app/data/claims_reference.db `
  -v C:\Users\shris\OneDrive\Documents\AI_Agents\.demo:/app/data `
  ai-agents-claims-api
```

## Railway

1. Push repo to GitHub.
2. Create Railway service from repo.
3. Railway uses `Dockerfile.api` via `railway.toml`.
4. Set environment variables:

```text
APP_VERSION=0.1.0
ENV=production
AI_AGENTS_REFERENCE_DB=/app/data/claims_reference.db
```

5. Attach/mount a persistent volume containing `claims_reference.db` if full NCCI is required.
6. Verify:

```text
GET /health
POST /api/v1/demo/scenarios/clean_em_837p/run
```
