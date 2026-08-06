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
The routing golden set currently contains 60 records and is guarded to stay in
the 50-80 record demo range. Coverage includes OIG precedence, seeded NCCI
CCMI-0 and CCMI-1 behavior, valid and invalid NCCI modifiers, E/M threshold
boundaries for all seeded 2026 codes, medical review routing, and clean
auto-pay cases.

Local deterministic golden tests run all 60 records. Expensive live evals use a
bounded smoke subset by default:

- `CLAIMS_AGENT_EVAL_SCOPE=smoke` or unset: use 12 representative records.
- `CLAIMS_AGENT_EVAL_SCOPE=full`: use all 60 records for release or nightly
  validation.

Measured on August 6, 2026 against the current Vertex endpoint:

- endpoint diff smoke: 12 live prediction calls.
- endpoint diff full: 60 live prediction calls, about 94 seconds.
- groundedness judge smoke: 3 synthetic + 8 real judge calls, about 171 seconds
  with `SARO_EVAL_JUDGE_SLEEP_SECONDS=2`.
- groundedness judge full: 3 synthetic + 30 real judge calls. Keep this for
  release/nightly runs, not default CI.

## Deployed endpoint diff

This catches drift between the local engine and the deployed Vertex image.
By default it calls the live endpoint for the smoke subset only. Set
`CLAIMS_AGENT_EVAL_SCOPE=full` to run all 60 records.

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
- `FAIL_UNKNOWN_DEPLOYMENT` / `FAIL_DRIFT_UNKNOWN_DEPLOYMENT`: the diff could
  not resolve deployment metadata, usually because the URL is not a Vertex
  predict URL or `gcloud` is unavailable. This fails closed once
  `CLAIMS_AGENT_ENDPOINT_URL` is configured.

CI exit policy:

- `PASS_CURRENT` and `PASS_STALE` exit 0.
- Every `FAIL_*` classification exits 1.
- If `CLAIMS_AGENT_ENDPOINT_URL` is unset, the deployed diff is explicitly
  skipped and exits 0.

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
By default it judges the smoke subset only after the synthetic fabrication
fixtures pass. Set `CLAIMS_AGENT_EVAL_SCOPE=full` for all real golden records.

The current `medical_necessity_check.reasoning` text is deterministic template
output, not model-generated text. A clean score on the real golden records
therefore validates judge plumbing and baseline grounding, not broad judge
quality.

Before judging real golden records, the harness runs permanent synthetic
fabrication fixtures from `evals/golden/groundedness_synthetic.jsonl`. These are
not routing golden records. They exist to prove the judge can catch a known bad
case before a clean run is trusted:

- `SYN-OBVIOUS-GC01`: must be caught as `FAIL_UNGROUNDED`.
- `SYN-INFERENCE-GC05` and `SYN-DEDUCTIBLE-GC06`: known blind-spot probes for
  inference-adjacent fabrications. They are visible in output but non-blocking
  unless the final classification is otherwise failing.

Environment variables:

- `SARO_EVAL_JUDGE=vertex`: explicit opt-in gate.
- `GOOGLE_CLOUD_PROJECT`: Google Cloud project ID.
- `GOOGLE_CLOUD_LOCATION`: Vertex location, for example `us-central1`.
- `GOOGLE_GENAI_USE_VERTEXAI=True`: makes `google-genai` use Vertex AI.
- `SARO_EVAL_JUDGE_SLEEP_SECONDS`: optional pacing delay between calls. Defaults
  to 10 seconds.
- `SARO_EVAL_JUDGE_RERUNS`: optional consistency reruns for any real golden
  record that lands in the boundary band or fails. Defaults to 3 total runs.
- `CLAIMS_AGENT_EVAL_SCOPE`: `smoke` by default, or `full` for all 60 routing
  golden records.

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

Groundedness classifications:

- `PASS_GROUNDED`: synthetic obvious fabrication was caught, and real golden
  records passed.
- `FLAG_BOUNDARY_REVIEW`: synthetic obvious fabrication was caught, but at least
  one synthetic blind-spot or real record landed in the 0.4-0.6 boundary band.
  Exit 0, but visible.
- `FAIL_UNGROUNDED`: obvious synthetic fabrication was not caught, or a real
  golden record failed. Exit 1.
