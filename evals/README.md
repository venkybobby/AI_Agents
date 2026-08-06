# Claims evals

The eval suite has three layers:

1. Local deterministic golden-label regression.
2. Opt-in deployed endpoint diff against the live Vertex container.
3. Opt-in Vertex Gemini groundedness judging for medical necessity reasoning.

Default CI runs only local deterministic checks. The deployed and judge checks
skip cleanly unless their environment variables are configured.

## Local golden eval

```powershell
python -m pytest evals/test_claims_evals.py -q
```

Golden records live in `evals/golden/claims_golden.jsonl`. Each record includes
`claim_data`, `expected_route`, `expected_gate`, and the business rationale.

## Deployed endpoint diff

This catches drift between the local engine and the deployed Vertex image.

Environment variables:

- `CLAIMS_AGENT_ENDPOINT_URL`: deployed endpoint base URL. If unset, the check
  prints `endpoint not configured, skipping drift check` and exits 0.
- `CLAIMS_AGENT_ENDPOINT_TOKEN`: optional bearer or identity token. This value is
  never printed.
- `CLAIMS_AGENT_DEPLOYED_IMAGE_URI`: optional override for the deployed image
  URI. If unset, the check resolves the live Vertex endpoint's active model
  through `gcloud`.
- `CLAIMS_AGENT_REPO_HEAD`: optional override for the repo HEAD short SHA.
  If unset, the check uses `git rev-parse --short HEAD`.

Run directly:

```bash
export CLAIMS_AGENT_ENDPOINT_URL="https://us-central1-aiplatform.googleapis.com/v1/projects/claimsanamolyagent/locations/us-central1/endpoints/ENDPOINT_ID:predict"
export CLAIMS_AGENT_ENDPOINT_TOKEN="$(gcloud auth print-access-token)"
python -m evals.deployed_endpoint_diff
```

The diff prints a deployment freshness classification before the optional
network proof:

- `PASS_CURRENT`: deployed image tag matches repo HEAD and all golden routes
  match.
- `PASS_STALE`: deployed image tag is behind repo HEAD, but all golden routes
  still match.
- `FAIL_DRIFT`: deployed image tag matches repo HEAD, but at least one golden
  route differs.
- `FAIL_STALE_AND_DRIFT`: deployed image tag is stale and at least one golden
  route differs.
- `PASS_UNKNOWN_DEPLOYMENT` / `FAIL_DRIFT_UNKNOWN_DEPLOYMENT`: the diff could
  not resolve deployment metadata, usually because the URL is not a Vertex
  predict URL or `gcloud` is unavailable.

Run through pytest:

```powershell
python -m pytest evals/test_deployed_diff.py -q
```

The deployed request reuses the app's existing Vertex `/predict` body shape:

```json
{
  "instances": [
    {
      "claim_data": {
        "claim_id": "GC-01",
        "provider_npi": "1234567890",
        "cpt_codes": ["99214"],
        "modifiers": [],
        "clinical_notes": "Moderate MDM documented with 35 minutes total time."
      }
    }
  ]
}
```

## Groundedness judge

This opt-in check evaluates `medical_necessity_check.reasoning` against the only
allowed context: `clinical_notes` plus the E/M requirement row.

Environment variables:

- `SARO_EVAL_JUDGE=vertex`: explicit opt-in gate.
- `GOOGLE_CLOUD_PROJECT`: Google Cloud project ID.
- `GOOGLE_CLOUD_LOCATION`: Vertex location, for example `us-central1`.
- `GOOGLE_GENAI_USE_VERTEXAI=True`: makes `google-genai` use Vertex AI.
- `SARO_EVAL_JUDGE_SLEEP_SECONDS`: optional pacing delay between calls. Defaults
  to 10 seconds.

Run directly:

```powershell
$env:SARO_EVAL_JUDGE = "vertex"
$env:GOOGLE_CLOUD_PROJECT = "claimsanamolyagent"
$env:GOOGLE_CLOUD_LOCATION = "us-central1"
$env:GOOGLE_GENAI_USE_VERTEXAI = "True"
python -m evals.groundedness_judge
```

Scores in the `0.4-0.6` boundary band are printed as human-review items and do
not fail CI. Outright failed groundedness scores exit 1.
