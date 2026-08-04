# Deploy the claims agent on Google Vertex AI

This service can run on Vertex AI as a custom prediction container. The
container exposes:

- `GET /health` for Vertex health checks.
- `POST /predict` for Vertex prediction requests.
- `POST /api/v1/claims/review-837` for normal REST/API use.

Vertex prediction body:

```json
{
  "instances": [
    {
      "edi_text": "ISA*00*..."
    }
  ]
}
```

## 1. Choose the reference data mode

For a quick demo, do nothing. If no full reference DB is present, the app
initializes the small seeded SQLite demo DB.

For full NCCI demo data, upload the local SQLite DB to Cloud Storage:

```bash
gcloud storage buckets create gs://YOUR_BUCKET --location=us-central1
gcloud storage cp .demo/claims_reference.db gs://YOUR_BUCKET/ncci/claims_reference.db
```

The Vertex container can download this at startup when these env vars are set:

```text
AI_AGENTS_REFERENCE_DB=/app/data/claims_reference.db
AI_AGENTS_REFERENCE_DB_GCS_URI=gs://YOUR_BUCKET/ncci/claims_reference.db
```

Grant the Vertex runtime service account `roles/storage.objectViewer` on the
bucket.

## Automated deployment

Use the checked-in deployment script from Cloud Shell or any Bash environment
with `gcloud` authenticated:

```bash
git clone https://github.com/venkybobby/AI_Agents.git
cd AI_Agents

PROJECT_ID="claimsanamolyagent" \
REGION="us-central1" \
./scripts/deploy_vertex.sh
```

If you only know the project number:

```bash
PROJECT_NUMBER="305101485369" ./scripts/deploy_vertex.sh
```

To deploy with the full NCCI SQLite DB loaded from Cloud Storage:

```bash
PROJECT_ID="claimsanamolyagent" \
REGION="us-central1" \
AI_AGENTS_REFERENCE_DB_GCS_URI="gs://YOUR_BUCKET/ncci/claims_reference.db" \
./scripts/deploy_vertex.sh
```

The script:

1. Enables required Google Cloud APIs.
2. Creates/reuses the Artifact Registry Docker repo.
3. Creates/reuses the Cloud Build staging bucket.
4. Grants Cloud Build and Vertex AI service agents the required IAM access.
5. Builds `Dockerfile.vertex` with Cloud Build.
6. Pushes the image to Artifact Registry.
7. Uploads a Vertex AI model with `/health` and `/predict` routes.
8. Creates/reuses the Vertex endpoint.
9. Deploys the model and prints `IMAGE`, `MODEL_ID`, and `ENDPOINT_ID`.

## GitHub Actions deployment

The repo also includes a manual workflow at `.github/workflows/deploy-vertex.yml`.
After Google Workload Identity Federation is configured, run it from GitHub
Actions with `workflow_dispatch`.

Required GitHub repository settings:

- Repository variable `GCP_PROJECT_ID`, for example `claimsanamolyagent`.
- Secret `GCP_WORKLOAD_IDENTITY_PROVIDER`.
- Secret `GCP_DEPLOY_SERVICE_ACCOUNT`.

The deploy service account needs permission to enable/read services, manage
Artifact Registry IAM, create Cloud Build builds, manage the staging bucket, and
upload/deploy Vertex AI models. In practice, use a dedicated deployment service
account and grant the minimum project/repository/bucket roles your organization
allows for those actions.

The workflow uses `google-github-actions/auth` with Workload Identity Federation
and `google-github-actions/setup-gcloud` to run the same
`scripts/deploy_vertex.sh` path used in Cloud Shell.

## Manual deployment

Use this section only when you need to run the deployment by hand or debug one
step at a time.

## 2. Configure Google Cloud

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable aiplatform.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com storage.googleapis.com
gcloud config set ai/region us-central1
```

Create an Artifact Registry Docker repo:

```bash
gcloud artifacts repositories create ai-agents \
  --repository-format=docker \
  --location=us-central1
```

## 3. Build and push the Vertex container

```bash
PROJECT_ID="YOUR_PROJECT_ID"
REGION="us-central1"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/ai-agents/claims-agent:$(git rev-parse --short HEAD)"

gcloud builds submit \
  --config cloudbuild.vertex.yaml \
  --substitutions="_IMAGE=$IMAGE" \
  .
```

## 4. Upload the container as a Vertex model

```bash
gcloud ai models upload \
  --region="$REGION" \
  --display-name=claims-agent \
  --container-image-uri="$IMAGE" \
  --container-ports=8080 \
  --container-health-route=/health \
  --container-predict-route=/predict \
  --container-env-vars=AI_AGENTS_REFERENCE_DB=/app/data/claims_reference.db,AI_AGENTS_REFERENCE_DB_GCS_URI=gs://YOUR_BUCKET/ncci/claims_reference.db
```

Capture the uploaded model ID:

```bash
MODEL_ID="$(gcloud ai models list \
  --region="$REGION" \
  --filter='displayName=claims-agent' \
  --sort-by=~createTime \
  --limit=1 \
  --format='value(name.basename())')"
```

## 5. Create an endpoint and deploy the model

```bash
gcloud ai endpoints create \
  --region="$REGION" \
  --display-name=claims-agent-endpoint

ENDPOINT_ID="$(gcloud ai endpoints list \
  --region="$REGION" \
  --filter='displayName=claims-agent-endpoint' \
  --sort-by=~createTime \
  --limit=1 \
  --format='value(name.basename())')"

gcloud ai endpoints deploy-model "$ENDPOINT_ID" \
  --region="$REGION" \
  --model="$MODEL_ID" \
  --display-name=claims-agent-v1 \
  --machine-type=e2-standard-4 \
  --min-replica-count=1 \
  --max-replica-count=2 \
  --traffic-split=0=100
```

## 6. Test online prediction

Create a local JSON request:

```bash
mkdir -p .demo
cat > .demo/vertex_request.json <<'EOF'
{
  "instances": [
    {
      "edi_text": "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *260729*1200*^*00501*000000905*0*T*:~GS*HC*SENDER*RECEIVER*20260729*1200*1*X*005010X222A1~ST*837*0001*005010X222A1~BHT*0019*00*CLAIM001*20260729*1200*CH~NM1*85*2*CLEAN CLINIC*****XX*1234567890~NM1*82*1*DOE*JANE****XX*1234567890~CLM*CLAIM001*250***11:B:1*Y*A*Y*I~HI*ABK:I10~LX*1~SV1*HC:99213*150*UN*1***1~NTE*ADD*moderate medical decision making 25 minutes documented~SE*11*0001~GE*1*1~IEA*1*000000905~"
    }
  ]
}
EOF
```

Run prediction:

```bash
gcloud ai endpoints predict "$ENDPOINT_ID" \
  --region="$REGION" \
  --json-request=.demo/vertex_request.json
```

Expected result: `predictions[0].route` should be `AUTO_PAY` for the clean
scenario.

## Production note

Vertex AI is appropriate for managed online prediction. For the Streamlit UI,
deploy it separately, for example on Cloud Run or Vercel, and call the Vertex
endpoint from the UI/backend. Do not put the UI inside the Vertex prediction
container.
