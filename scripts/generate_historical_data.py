"""
Vertex AI modelini egitmek icin BigQuery'ye toplu sentetik gecmis veri yukler.
Canli simulatorden farkli olarak Cloud Run'a tek tek istek atmaz; pandas
DataFrame'i dogrudan BigQuery'ye yukler (cok daha hizli).

is_anomaly kolonu burada "ground truth" (enjekte ettigimiz bilinen ariza)
olarak kullanilir; boylece egitim sonrasi modelin bu enjekte edilmis
anomalileri ne kadar yakaladigini olcebiliriz. Canli akista ayni kolon
modelin tahminini tutar.
"""

import argparse
import random
from datetime import datetime, timedelta, timezone

import pandas as pd
from google.cloud import bigquery

BASE_TEMP = 45.0
BASE_VIBRATION = 12.0
BASE_POWER = 220.0


def generate_rows(num_rows: int, device_id: str, anomaly_probability: float, interval_minutes: int):
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=interval_minutes * num_rows)

    rows = []
    ts = start
    for _ in range(num_rows):
        anomaly = random.random() < anomaly_probability
        if anomaly:
            motor_sicakligi = BASE_TEMP + random.uniform(25, 45)
            titresim_frekansi = BASE_VIBRATION + random.uniform(15, 30)
            guc_tuketimi = BASE_POWER + random.uniform(80, 150)
        else:
            motor_sicakligi = BASE_TEMP + random.gauss(0, 2)
            titresim_frekansi = BASE_VIBRATION + random.gauss(0, 1)
            guc_tuketimi = BASE_POWER + random.gauss(0, 8)

        rows.append(
            {
                "timestamp": ts,
                "device_id": device_id,
                "motor_sicakligi": round(motor_sicakligi, 2),
                "titresim_frekansi": round(titresim_frekansi, 2),
                "guc_tuketimi": round(guc_tuketimi, 2),
                "ingest_timestamp": end,
                "is_anomaly": anomaly,
                "anomaly_score": None,
            }
        )
        ts += timedelta(minutes=interval_minutes)

    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--dataset", default="telemetry")
    parser.add_argument("--table", default="sensor_readings")
    parser.add_argument("--device-id", default="vestel-motor-001")
    parser.add_argument("--num-rows", type=int, default=8000)
    parser.add_argument("--anomaly-probability", type=float, default=0.03)
    parser.add_argument("--interval-minutes", type=int, default=3)
    args = parser.parse_args()

    df = generate_rows(args.num_rows, args.device_id, args.anomaly_probability, args.interval_minutes)
    print(f"Uretilen satir sayisi: {len(df)} (anomali: {df['is_anomaly'].sum()})")

    client = bigquery.Client(project=args.project)
    table_ref = f"{args.project}.{args.dataset}.{args.table}"

    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_APPEND")
    load_job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
    load_job.result()

    print(f"Yuklendi -> {table_ref}")


if __name__ == "__main__":
    main()
