#!/usr/bin/env bash
set -e

PROJECT_ID=$(gcloud config get-value project)
REGION="europe-west1"
SERVICE_NAME="pdm-ingest-api"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== Cloud Run'a deploy ediliyor: ${SERVICE_NAME} (${REGION}) =="
gcloud run deploy "$SERVICE_NAME" \
  --source="${SCRIPT_DIR}/../cloud-run-api" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --allow-unauthenticated \
  --set-env-vars="BQ_DATASET=telemetry,BQ_TABLE=sensor_readings,BQ_ALERTS_TABLE=acil_bakim_uyarilari,MODEL_GCS_PATH=gs://${PROJECT_ID}-pdm-artifacts/models/isolation_forest/model.joblib"

echo ""
echo "== Servis URL'i =="
gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format="value(status.url)"
