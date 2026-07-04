#!/bin/bash
# deploy_gcp.sh
# Bash Script to build and deploy the Neaty File Organizer Agent to Google Cloud Platform (GCP).
# Project ID: annular-aria-499706-f1

set -e

PROJECT_ID="annular-aria-499706-f1"
REGION="us-central1"
SERVICE_NAME="neaty-agent"
IMAGE_TAG="gcr.io/$PROJECT_ID/$SERVICE_NAME:latest"

echo "=========================================================="
echo "🚀 Starting Deployment of Neaty Agent to GCP"
echo "Project ID: $PROJECT_ID"
echo "Region:     $REGION"
echo "=========================================================="

# 1. Verify gcloud installation
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: Google Cloud SDK (gcloud CLI) is not installed or not in your PATH."
    echo "Please install it from: https://cloud.google.com/sdk"
    exit 1
fi

# 2. Check and set GCP Project
echo "📍 Configuring gcloud active project..."
gcloud config set project "$PROJECT_ID"

# 3. Enable necessary GCP APIs
echo "⚙️ Enabling necessary Google Cloud Service APIs..."
echo "(This might take a minute if this is a fresh project...)"
gcloud services enable run.googleapis.com \
                       pubsub.googleapis.com \
                       artifactregistry.googleapis.com \
                       cloudbuild.googleapis.com

# 4. Build and push container to Google Container Registry via Cloud Build
echo "📦 Building and pushing container image to Google Container Registry..."
echo "This uploads the source code and compiles the Docker image on Google Cloud..."
gcloud builds submit --tag "$IMAGE_TAG" .

# 5. Deploy the container to Google Cloud Run
echo "🚢 Deploying container to Google Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE_TAG" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,ENABLE_GCP_PUBSUB=TRUE,GOOGLE_GENAI_USE_ENTERPRISE=TRUE,GOOGLE_CLOUD_LOCATION=$REGION"

echo ""
echo "=========================================================="
echo "🎉 SUCCESS: Neaty Agent deployed successfully!"
echo "You can access your web playground using the Cloud Run Service URL listed above."
echo "The background Pub/Sub worker was initialized inside the container."
echo "=========================================================="
