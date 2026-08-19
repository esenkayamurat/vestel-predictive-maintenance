import os
import tempfile
from datetime import datetime, timezone

import joblib
from fastapi import FastAPI, HTTPException
from google.cloud import bigquery, storage
from pydantic import BaseModel, Field

app = FastAPI(title="Vestel PdM Ingestion API")

DATASET = os.environ.get("BQ_DATASET", "telemetry")
TABLE = os.environ.get("BQ_TABLE", "sensor_readings")
ALERTS_TABLE = os.environ.get("BQ_ALERTS_TABLE", "acil_bakim_uyarilari")
MODEL_GCS_PATH = os.environ.get("MODEL_GCS_PATH")

bq_client = bigquery.Client()
TABLE_REF = f"{bq_client.project}.{DATASET}.{TABLE}"
ALERTS_TABLE_REF = f"{bq_client.project}.{DATASET}.{ALERTS_TABLE}"


def load_model(gcs_path: str):
    """Vertex AI'da egitilip GCS'ye yazilan modeli container ayaga kalkarken
    bir kere indirip bellekte tutar; her istekte GCS'ye gitmeyiz."""
    assert gcs_path.startswith("gs://"), "MODEL_GCS_PATH gs:// ile baslamali"
    bucket_name, _, blob_path = gcs_path[len("gs://") :].partition("/")

    storage_client = storage.Client()
    with tempfile.NamedTemporaryFile(suffix=".joblib") as tmp:
        storage_client.bucket(bucket_name).blob(blob_path).download_to_filename(tmp.name)
        return joblib.load(tmp.name)


model = load_model(MODEL_GCS_PATH) if MODEL_GCS_PATH else None


class TelemetryReading(BaseModel):
    timestamp: datetime
    device_id: str = Field(min_length=1)
    motor_sicakligi: float
    titresim_frekansi: float
    guc_tuketimi: float


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model is not None}


@app.post("/ingest")
def ingest(reading: TelemetryReading):
    is_anomaly = None
    anomaly_score = None

    if model is not None:
        features = [[reading.motor_sicakligi, reading.titresim_frekansi, reading.guc_tuketimi]]
        is_anomaly = bool(model.predict(features)[0] == -1)  # -1 = anomali, 1 = normal
        anomaly_score = float(model.decision_function(features)[0])  # dusuk skor = daha anormal

    ingest_timestamp = datetime.now(timezone.utc)
    row = {
        "timestamp": reading.timestamp.isoformat(),
        "device_id": reading.device_id,
        "motor_sicakligi": reading.motor_sicakligi,
        "titresim_frekansi": reading.titresim_frekansi,
        "guc_tuketimi": reading.guc_tuketimi,
        "ingest_timestamp": ingest_timestamp.isoformat(),
        "is_anomaly": is_anomaly,
        "anomaly_score": anomaly_score,
    }

    errors = bq_client.insert_rows_json(TABLE_REF, [row])
    if errors:
        raise HTTPException(status_code=500, detail=errors)

    if is_anomaly:
        alert_row = {
            "device_id": reading.device_id,
            "reading_timestamp": reading.timestamp.isoformat(),
            "detected_at": ingest_timestamp.isoformat(),
            "motor_sicakligi": reading.motor_sicakligi,
            "titresim_frekansi": reading.titresim_frekansi,
            "guc_tuketimi": reading.guc_tuketimi,
            "anomaly_score": anomaly_score,
        }
        alert_errors = bq_client.insert_rows_json(ALERTS_TABLE_REF, [alert_row])
        if alert_errors:
            raise HTTPException(status_code=500, detail=alert_errors)

    return {
        "status": "accepted",
        "device_id": reading.device_id,
        "is_anomaly": is_anomaly,
        "anomaly_score": anomaly_score,
    }
