#!/usr/bin/env bash
set -euo pipefail

# Deploy the claims anomaly agent to Vertex AI as a custom prediction container.
#
# Required:
#   PROJECT_ID or PROJECT_NUMBER
#
# Optional:
#   REGION=us-central1
#   REPOSITORY=ai-agents
#   IMAGE_NAME=claims-agent
#   MODEL_DISPLAY_NAME=claims-agent
#   ENDPOINT_DISPLAY_NAME=claims-agent-endpoint
#   DEPLOYED_MODEL_DISPLAY_NAME=claims-agent-v1
#   MACHINE_TYPE=e2-standard-4
#   MIN_REPLICA_COUNT=1
#   MAX_REPLICA_COUNT=2
#   STAGING_BUCKET=<project-id>-cloudbuild-staging
#   AI_AGENTS_REFERENCE_DB_GCS_URI=gs://bucket/path/claims_reference.db

REGION="${REGION:-us-central1}"
REPOSITORY="${REPOSITORY:-ai-agents}"
IMAGE_NAME="${IMAGE_NAME:-claims-agent}"
MODEL_DISPLAY_NAME="${MODEL_DISPLAY_NAME:-claims-agent}"
ENDPOINT_DISPLAY_NAME="${ENDPOINT_DISPLAY_NAME:-claims-agent-endpoint}"
DEPLOYED_MODEL_DISPLAY_NAME="${DEPLOYED_MODEL_DISPLAY_NAME:-claims-agent-v1}"
MACHINE_TYPE="${MACHINE_TYPE:-e2-standard-4}"
MIN_REPLICA_COUNT="${MIN_REPLICA_COUNT:-1}"
MAX_REPLICA_COUNT="${MAX_REPLICA_COUNT:-2}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

log() {
  printf '\n[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required command: $1" >&2
    exit 2
  fi
}

resolve_project() {
  if [[ -n "${PROJECT_ID:-}" ]]; then
    return
  fi

  if [[ -n "${PROJECT_NUMBER:-}" ]]; then
    PROJECT_ID="$(gcloud projects describe "$PROJECT_NUMBER" --format='value(projectId)')"
    export PROJECT_ID
    return
  fi

  local configured_project
  configured_project="$(gcloud config get-value project 2>/dev/null || true)"
  if [[ -z "$configured_project" || "$configured_project" == "(unset)" ]]; then
    echo "PROJECT_ID or PROJECT_NUMBER is required, or set gcloud config project." >&2
    exit 2
  fi

  if [[ "$configured_project" =~ ^[0-9]+$ ]]; then
    PROJECT_NUMBER="$configured_project"
    PROJECT_ID="$(gcloud projects describe "$PROJECT_NUMBER" --format='value(projectId)')"
  else
    PROJECT_ID="$configured_project"
  fi
  export PROJECT_ID
}

grant_repo_role() {
  local member="$1"
  local role="$2"
  gcloud artifacts repositories add-iam-policy-binding "$REPOSITORY" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --member="$member" \
    --role="$role" >/dev/null
}

grant_bucket_role() {
  local bucket="$1"
  local member="$2"
  local role="$3"
  gcloud storage buckets add-iam-policy-binding "gs://$bucket" \
    --project="$PROJECT_ID" \
    --member="$member" \
    --role="$role" >/dev/null
}

require_cmd gcloud
require_cmd git

resolve_project
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
STAGING_BUCKET="${STAGING_BUCKET:-${PROJECT_ID}-cloudbuild-staging}"
COMMIT_SHA="$(git rev-parse --short HEAD)"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:${COMMIT_SHA}"
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
VERTEX_SA="service-${PROJECT_NUMBER}@gcp-sa-aiplatform.iam.gserviceaccount.com"

log "project_id=$PROJECT_ID project_number=$PROJECT_NUMBER region=$REGION"
gcloud config set project "$PROJECT_ID" >/dev/null
gcloud config set ai/region "$REGION" >/dev/null

log "enabling required Google Cloud APIs"
gcloud services enable \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  storage.googleapis.com \
  --project="$PROJECT_ID" >/dev/null

log "creating/reusing Artifact Registry repository: $REPOSITORY"
if ! gcloud artifacts repositories describe "$REPOSITORY" \
  --project="$PROJECT_ID" \
  --location="$REGION" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$REPOSITORY" \
    --project="$PROJECT_ID" \
    --repository-format=docker \
    --location="$REGION" >/dev/null
fi

log "creating/reusing Cloud Build staging bucket: gs://$STAGING_BUCKET"
if ! gcloud storage buckets describe "gs://$STAGING_BUCKET" \
  --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://$STAGING_BUCKET" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --uniform-bucket-level-access >/dev/null
fi

log "granting Cloud Build runtime service accounts access"
grant_bucket_role "$STAGING_BUCKET" "serviceAccount:$COMPUTE_SA" "roles/storage.objectViewer"
grant_bucket_role "$STAGING_BUCKET" "serviceAccount:$CLOUDBUILD_SA" "roles/storage.objectViewer"
grant_repo_role "serviceAccount:$COMPUTE_SA" "roles/artifactregistry.writer"
grant_repo_role "serviceAccount:$CLOUDBUILD_SA" "roles/artifactregistry.writer"

log "granting Vertex AI service agent image pull access"
grant_repo_role "serviceAccount:$VERTEX_SA" "roles/artifactregistry.reader"

if [[ -n "${AI_AGENTS_REFERENCE_DB_GCS_URI:-}" ]]; then
  if [[ ! "$AI_AGENTS_REFERENCE_DB_GCS_URI" =~ ^gs://([^/]+)/(.+)$ ]]; then
    echo "AI_AGENTS_REFERENCE_DB_GCS_URI must be gs://bucket/object" >&2
    exit 2
  fi
  REFERENCE_BUCKET="${BASH_REMATCH[1]}"
  log "granting Vertex AI service agent reference DB read access: gs://$REFERENCE_BUCKET"
  grant_bucket_role "$REFERENCE_BUCKET" "serviceAccount:$VERTEX_SA" "roles/storage.objectViewer"
fi

log "building and pushing image: $IMAGE"
gcloud builds submit \
  --project="$PROJECT_ID" \
  --config cloudbuild.vertex.yaml \
  --substitutions="_IMAGE=$IMAGE" \
  --gcs-source-staging-dir="gs://$STAGING_BUCKET/source" \
  .

MODEL_ENV_ARGS=()
if [[ -n "${AI_AGENTS_REFERENCE_DB_GCS_URI:-}" ]]; then
  MODEL_ENV_ARGS+=(
    "--container-env-vars=AI_AGENTS_REFERENCE_DB=/app/data/claims_reference.db,AI_AGENTS_REFERENCE_DB_GCS_URI=${AI_AGENTS_REFERENCE_DB_GCS_URI}"
  )
fi

log "uploading Vertex AI model: $MODEL_DISPLAY_NAME"
gcloud ai models upload \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --display-name="$MODEL_DISPLAY_NAME" \
  --container-image-uri="$IMAGE" \
  --container-ports=8080 \
  --container-health-route=/health \
  --container-predict-route=/predict \
  "${MODEL_ENV_ARGS[@]}"

MODEL_ID="$(gcloud ai models list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --filter="displayName=${MODEL_DISPLAY_NAME}" \
  --sort-by=~createTime \
  --limit=1 \
  --format='value(name.basename())')"

if [[ -z "$MODEL_ID" ]]; then
  echo "model upload completed, but MODEL_ID could not be resolved" >&2
  exit 1
fi

log "creating/reusing Vertex AI endpoint: $ENDPOINT_DISPLAY_NAME"
ENDPOINT_ID="$(gcloud ai endpoints list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --filter="displayName=${ENDPOINT_DISPLAY_NAME}" \
  --sort-by=~createTime \
  --limit=1 \
  --format='value(name.basename())')"

if [[ -z "$ENDPOINT_ID" ]]; then
  gcloud ai endpoints create \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --display-name="$ENDPOINT_DISPLAY_NAME"
  ENDPOINT_ID="$(gcloud ai endpoints list \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --filter="displayName=${ENDPOINT_DISPLAY_NAME}" \
    --sort-by=~createTime \
    --limit=1 \
    --format='value(name.basename())')"
fi

if [[ -z "$ENDPOINT_ID" ]]; then
  echo "endpoint create completed, but ENDPOINT_ID could not be resolved" >&2
  exit 1
fi

log "deploying model $MODEL_ID to endpoint $ENDPOINT_ID"
gcloud ai endpoints deploy-model "$ENDPOINT_ID" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --model="$MODEL_ID" \
  --display-name="$DEPLOYED_MODEL_DISPLAY_NAME" \
  --machine-type="$MACHINE_TYPE" \
  --min-replica-count="$MIN_REPLICA_COUNT" \
  --max-replica-count="$MAX_REPLICA_COUNT" \
  --traffic-split=0=100

log "deployment complete"
cat <<EOF
IMAGE=$IMAGE
MODEL_ID=$MODEL_ID
ENDPOINT_ID=$ENDPOINT_ID

Smoke test:
  gcloud ai endpoints predict "$ENDPOINT_ID" \\
    --project="$PROJECT_ID" \\
    --region="$REGION" \\
    --json-request=.demo/vertex_request.json

Local deployed-drift eval:
  export CLAIMS_AGENT_ENDPOINT_URL="https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/endpoints/${ENDPOINT_ID}:predict"
  export CLAIMS_AGENT_ENDPOINT_TOKEN="\$(gcloud auth print-access-token)"
  python -m evals.deployed_endpoint_diff
EOF
