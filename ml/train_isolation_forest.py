"""
Vertex AI Custom Training Job olarak calisir (managed compute uzerinde).
BigQuery'deki sensor_readings tablosundan okur, sklearn IsolationForest
egitir ve joblib model dosyasini GCS'ye yazar.
"""

import argparse
import tempfile
from pathlib import Path

import joblib
from google.cloud import bigquery, storage
from sklearn.ensemble import IsolationForest

FEATURE_COLUMNS = ["motor_sicakligi", "titresim_frekansi", "guc_tuketimi"]


def load_training_data(project: str, dataset: str, table: str):
    client = bigquery.Client(project=project)
    query = f"""
        SELECT {", ".join(FEATURE_COLUMNS)}, is_anomaly
        FROM `{project}.{dataset}.{table}`
    """
    return client.query(query).to_dataframe()


def upload_to_gcs(local_path: str, gcs_dir: str):
    assert gcs_dir.startswith("gs://")
    bucket_name, _, prefix = gcs_dir[len("gs://") :].partition("/")
    blob_path = f"{prefix.rstrip('/')}/model.joblib" if prefix else "model.joblib"

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.upload_from_filename(local_path)
    print(f"Model yuklendi -> gs://{bucket_name}/{blob_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--dataset", default="telemetry")
    parser.add_argument("--table", default="sensor_readings")
    parser.add_argument("--model-dir", required=True, help="gs://bucket/path")
    parser.add_argument("--contamination", type=float, default=0.03)
    args = parser.parse_args()

    df = load_training_data(args.project, args.dataset, args.table)
    print(f"Egitim verisi: {len(df)} satir")

    X = df[FEATURE_COLUMNS].to_numpy()

    model = IsolationForest(
        n_estimators=200,
        contamination=args.contamination,
        random_state=42,
    )
    model.fit(X)

    if "is_anomaly" in df.columns and df["is_anomaly"].notna().any():
        predictions = model.predict(X)  # -1 = anomali, 1 = normal
        predicted_anomaly = predictions == -1
        ground_truth = df["is_anomaly"].fillna(False).astype(bool)

        true_positive = (predicted_anomaly & ground_truth).sum()
        false_positive = (predicted_anomaly & ~ground_truth).sum()
        false_negative = (~predicted_anomaly & ground_truth).sum()
        total_ground_truth = ground_truth.sum()

        precision = true_positive / max(predicted_anomaly.sum(), 1)
        recall = true_positive / max(total_ground_truth, 1)

        print(f"Ground truth anomali sayisi: {total_ground_truth}")
        print(f"Yakalanan (true positive): {true_positive}")
        print(f"Yanlis alarm (false positive): {false_positive}")
        print(f"Kacirilan (false negative): {false_negative}")
        print(f"Precision: {precision:.3f} | Recall: {recall:.3f}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        local_path = str(Path(tmp_dir) / "model.joblib")
        joblib.dump(model, local_path)
        upload_to_gcs(local_path, args.model_dir)

    print("Egitim tamamlandi.")


if __name__ == "__main__":
    main()
