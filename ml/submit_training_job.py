"""
Lokal laptoptan calisir; egitimi Vertex AI'in yonetilen (managed) compute'una
gonderir. Bu script kendisi model egitmez, sadece isi Vertex AI'a teslim eder.
"""

import argparse

from google.cloud import aiplatform


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", default="europe-west1")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--dataset", default="telemetry")
    parser.add_argument("--table", default="sensor_readings")
    parser.add_argument(
        "--training-image",
        default=None,
        help="gcloud builds submit ile Artifact Registry'e itilen egitim container'inin URI'si "
        "(varsayilan: <region>-docker.pkg.dev/<project>/pdm-training/isolation-forest-trainer:latest)",
    )
    args = parser.parse_args()

    training_image = args.training_image or (
        f"{args.region}-docker.pkg.dev/{args.project}/pdm-training/isolation-forest-trainer:latest"
    )

    aiplatform.init(project=args.project, location=args.region, staging_bucket=f"gs://{args.bucket}")

    model_dir = f"gs://{args.bucket}/models/isolation_forest"

    # Vertex AI'in hazir scikit-learn training container'lari destegi kesildigi (deprecated)
    # icin kendi egitim image'imizi (ml/Dockerfile) kullaniyoruz.
    job = aiplatform.CustomContainerTrainingJob(
        display_name="pdm-isolation-forest-training",
        container_uri=training_image,
    )

    job.run(
        args=[
            f"--project={args.project}",
            f"--dataset={args.dataset}",
            f"--table={args.table}",
            f"--model-dir={model_dir}",
        ],
        replica_count=1,
        machine_type="n1-standard-4",
        sync=True,
    )

    print(f"Egitim tamamlandi. Model: {model_dir}/model.joblib")


if __name__ == "__main__":
    main()
