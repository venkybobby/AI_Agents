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

Run directly:

```powershell
$env:CLAIMS_AGENT_ENDPOINT_URL = "https://YOUR_ENDPOINT_BASE_URL"
python -m evals.deployed_endpoint_diff
```

Run through pytest:

```powershell
python -m pytest evals/test_deployed_diff.py -q
```

The deployed request reuses the app's existing Vertex `/predict` shape:

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
