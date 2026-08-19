#!/usr/bin/env bash
set -e

PROJECT_ID=$(gcloud config get-value project)
REGION="europe-west1"
BUCKET="${PROJECT_ID}-pdm-artifacts"

echo "== GCS bucket olusturuluyor: gs://${BUCKET} =="
gcloud storage buckets create "gs://${BUCKET}" --location="$REGION" --project="$PROJECT_ID" \
  || echo "Bucket zaten var, atlaniyor"

echo "== Tamamlandi =="
echo "BUCKET: ${BUCKET}"
echo "$BUCKET" > "$HOME/.vestel-pdm-bucket"
