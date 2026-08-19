#!/usr/bin/env bash
set -e

PROJECT_ID=$(gcloud config get-value project)
DATASET="telemetry"
TABLE="sensor_readings"
LOCATION="EU"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== Dataset olusturuluyor: ${PROJECT_ID}:${DATASET} =="
bq --location="$LOCATION" mk --dataset "${PROJECT_ID}:${DATASET}" || echo "Dataset zaten var, atlaniyor"

echo "== Tablo olusturuluyor: ${DATASET}.${TABLE} (DATE(timestamp) ile partitioned, device_id ile clustered) =="
bq mk --table \
  --time_partitioning_field timestamp \
  --time_partitioning_type DAY \
  --clustering_fields device_id \
  "${PROJECT_ID}:${DATASET}.${TABLE}" \
  "${SCRIPT_DIR}/../bigquery/schema.json" || echo "Tablo zaten var, atlaniyor"

echo "== Acil bakim uyari tablosu olusturuluyor: ${DATASET}.acil_bakim_uyarilari =="
bq mk --table \
  --time_partitioning_field detected_at \
  --time_partitioning_type DAY \
  --clustering_fields device_id \
  "${PROJECT_ID}:${DATASET}.acil_bakim_uyarilari" \
  "${SCRIPT_DIR}/../bigquery/alerts_schema.json" || echo "Tablo zaten var, atlaniyor"

echo "== Tamamlandi =="
bq show --format=prettyjson "${PROJECT_ID}:${DATASET}.${TABLE}" | head -30
