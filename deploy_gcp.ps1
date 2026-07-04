# deploy_gcp.ps1
# PowerShell Script to build and deploy the Neaty File Organizer Agent to Google Cloud Platform (GCP).
# Project ID: annular-aria-499706-f1

# Force UTF-8 Output
$OutputEncoding = [System.Text.Encoding]::UTF8

# Configure Proxy for Google Cloud bypass (Nekoray/Clash)
# $env:HTTP_PROXY="http://127.0.0.1:10809"
# $env:HTTPS_PROXY="http://127.0.0.1:10809"

$PROJECT_ID = "annular-aria-499706-f1"
$REGION = "us-central1"
$SERVICE_NAME = "neaty-agent"
$IMAGE_TAG = "gcr.io/" + $PROJECT_ID + "/" + $SERVICE_NAME + ":latest"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Starting Deployment of Neaty Agent to GCP" -ForegroundColor Cyan
Write-Host "Project ID: $PROJECT_ID" -ForegroundColor Cyan
Write-Host "Region:     $REGION" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Verify gcloud installation
$gcloudCheck = Get-Command gcloud -ErrorAction SilentlyContinue
if (-not $gcloudCheck) {
    Write-Error "Google Cloud SDK (gcloud CLI) is not installed or not in your PATH. Please install it from: https://cloud.google.com/sdk"
    Exit 1
}

# 2. Check and set GCP Project
Write-Host "Configuring gcloud active project..." -ForegroundColor Yellow
gcloud config set project $PROJECT_ID
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to set GCP project. Please make sure you are authenticated by running: gcloud auth login"
    Exit 1
}

# 3. Enable necessary GCP APIs
Write-Host "Enabling necessary Google Cloud Service APIs..." -ForegroundColor Yellow
Write-Host "(This might take a minute if this is a fresh project...)" -ForegroundColor Gray
gcloud services enable run.googleapis.com `
                       pubsub.googleapis.com `
                       artifactregistry.googleapis.com `
                       cloudbuild.googleapis.com
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to enable GCP service APIs. Verify your account has Project Editor permissions."
    Exit 1
}

# 4. Build and push container to Google Container Registry via Cloud Build
Write-Host "Building and pushing container image to Google Container Registry..." -ForegroundColor Yellow
Write-Host "This uploads the source code and compiles the Docker image on Google Cloud..." -ForegroundColor Gray
gcloud builds submit --tag $IMAGE_TAG .
if ($LASTEXITCODE -ne 0) {
    Write-Error "Cloud Build failed. Check the errors above or check your network/proxy settings."
    Exit 1
}

# 5. Deploy the container to Google Cloud Run
Write-Host "Deploying container to Google Cloud Run..." -ForegroundColor Yellow
gcloud run deploy $SERVICE_NAME `
  --image $IMAGE_TAG `
  --platform managed `
  --region $REGION `
  --allow-unauthenticated `
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,ENABLE_GCP_PUBSUB=TRUE,GOOGLE_GENAI_USE_ENTERPRISE=TRUE,GOOGLE_CLOUD_LOCATION=$REGION"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Deployment to Google Cloud Run failed."
    Exit 1
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "SUCCESS: Neaty Agent deployed successfully!" -ForegroundColor Green
Write-Host "You can access your web playground using the Cloud Run Service URL listed above." -ForegroundColor Green
Write-Host "The background Pub/Sub worker was initialized inside the container." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
