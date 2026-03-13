#!/usr/bin/env bash
# ============================================
# Cloudboosta Voice Agent — Cloud Run Deploy
# Quick deployment using gcloud CLI
# ============================================
set -euo pipefail

# --- Configuration (override via environment) ---
PROJECT_ID="${GCP_PROJECT_ID:-vision-gridai}"
REGION="${GCP_REGION:-europe-west1}"
SERVICE_NAME="${SERVICE_NAME:-cloudboosta-voice-agent}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
REPO_NAME="${SERVICE_NAME}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:${IMAGE_TAG}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[deploy]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[error]${NC} $*" >&2; }

# --- Preflight checks ---
log "Preflight checks..."

if ! command -v gcloud &>/dev/null; then
  err "gcloud CLI not found. Install: https://cloud.google.com/sdk/docs/install"
  exit 1
fi

if ! command -v docker &>/dev/null; then
  err "Docker not found."
  exit 1
fi

# Verify gcloud project
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
if [[ "$CURRENT_PROJECT" != "$PROJECT_ID" ]]; then
  warn "Switching gcloud project from '${CURRENT_PROJECT}' to '${PROJECT_ID}'"
  gcloud config set project "$PROJECT_ID"
fi

# --- Step 1: Enable APIs (idempotent) ---
log "Enabling required APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  --quiet

# --- Step 2: Create Artifact Registry repo (idempotent) ---
log "Creating Artifact Registry repo '${REPO_NAME}'..."
gcloud artifacts repositories describe "$REPO_NAME" \
  --location="$REGION" &>/dev/null 2>&1 || \
gcloud artifacts repositories create "$REPO_NAME" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Cloudboosta Voice Agent images" \
  --quiet

# --- Step 3: Configure Docker auth ---
log "Configuring Docker for Artifact Registry..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# --- Step 4: Build Docker image ---
log "Building Docker image..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

docker build -t "$IMAGE" "$PROJECT_ROOT"

# --- Step 5: Push image ---
log "Pushing image to Artifact Registry..."
docker push "$IMAGE"

# --- Step 6: Create secrets (idempotent) ---
create_secret() {
  local name="$1"
  local env_var="$2"
  local value="${!env_var:-}"

  if [[ -z "$value" ]]; then
    warn "Env var ${env_var} not set, skipping secret '${name}'"
    return
  fi

  # Create secret if it doesn't exist
  if ! gcloud secrets describe "$name" &>/dev/null 2>&1; then
    log "Creating secret '${name}'..."
    printf '%s' "$value" | gcloud secrets create "$name" --data-file=- --quiet
  else
    log "Updating secret '${name}'..."
    printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=- --quiet
  fi
}

create_secret "${SERVICE_NAME}-google-api-key" "GOOGLE_API_KEY"
create_secret "${SERVICE_NAME}-supabase-url" "SUPABASE_URL"
create_secret "${SERVICE_NAME}-supabase-service-key" "SUPABASE_SERVICE_KEY"
create_secret "${SERVICE_NAME}-twilio-account-sid" "TWILIO_ACCOUNT_SID"
create_secret "${SERVICE_NAME}-twilio-auth-token" "TWILIO_AUTH_TOKEN"
create_secret "${SERVICE_NAME}-twilio-phone" "TWILIO_PHONE_NUMBER"

# --- Step 7: Create service account (idempotent) ---
SA_NAME="${SERVICE_NAME}-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe "$SA_EMAIL" &>/dev/null 2>&1; then
  log "Creating service account '${SA_NAME}'..."
  gcloud iam service-accounts create "$SA_NAME" \
    --display-name="Cloudboosta Voice Agent" \
    --quiet
fi

# Grant roles (idempotent)
for ROLE in roles/datastore.user roles/secretmanager.secretAccessor roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$ROLE" \
    --condition=None \
    --quiet &>/dev/null
done
log "Service account configured: ${SA_EMAIL}"

# --- Step 8: Deploy to Cloud Run ---
GEMINI_MODEL="${GEMINI_MODEL:-gemini-2.5-flash-native-audio-latest}"

log "Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --image="$IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --service-account="$SA_EMAIL" \
  --allow-unauthenticated \
  --port=8080 \
  --timeout=900 \
  --session-affinity \
  --min-instances=0 \
  --max-instances=2 \
  --memory=512Mi \
  --cpu=1 \
  --set-secrets="GOOGLE_API_KEY=${SERVICE_NAME}-google-api-key:latest,SUPABASE_URL=${SERVICE_NAME}-supabase-url:latest,SUPABASE_SERVICE_KEY=${SERVICE_NAME}-supabase-service-key:latest,TWILIO_ACCOUNT_SID=${SERVICE_NAME}-twilio-account-sid:latest,TWILIO_AUTH_TOKEN=${SERVICE_NAME}-twilio-auth-token:latest,TWILIO_PHONE_NUMBER=${SERVICE_NAME}-twilio-phone:latest" \
  --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION},GEMINI_MODEL=${GEMINI_MODEL},GOOGLE_GENAI_USE_VERTEXAI=false" \
  --quiet

# --- Step 9: Get service URL ---
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region="$REGION" \
  --format="value(status.url)")

echo ""
log "=========================================="
log "Deployment complete!"
log "Service URL: ${SERVICE_URL}"
log "Health check: ${SERVICE_URL}/health"
log "=========================================="
