# Vestel Uçtan Buluta Kestirimci Bakım (Predictive Maintenance)

Fedora Linux laptop üzerinden, gerçek bir Vestel IoT/Cloud/Big Data/AI mimarisinin uçtan uca minyatür bir simülasyonu: bir "cihaz" sentetik motor telemetrisi üretir, bulutta senkron olarak Vertex AI'da eğitilmiş bir anomali tespit modeliyle değerlendirilir, sonuç BigQuery'ye ve gerektiğinde ayrı bir "acil bakım" tablosuna yazılır.

GCP proje: `vestel-pdm-7883` — bölge: `europe-west1`
Deploy edilmiş servis: `https://pdm-ingest-api-191805562758.europe-west1.run.app`
GitHub: `https://github.com/esenkayamurat/vestel-predictive-maintenance`

## Mimari

```
edge-simulator (Podman, laptop)
      │  HTTP POST /ingest
      ▼
cloud-run-api (Cloud Run, FastAPI)
      │  1) modeli GCS'den bir kez belleğe yükler (cold start)
      │  2) her istekte in-process IsolationForest.predict()
      ▼                                   ▲
BigQuery: telemetry.sensor_readings       │ egitim verisi
      │  is_anomaly ise                   │
      ▼                                   │
BigQuery: telemetry.acil_bakim_uyarilari  │
                                           │
ml/train_isolation_forest.py ─────────────┘
  (Vertex AI CustomContainerTrainingJob ile
   managed compute'da calisir, modeli GCS'ye yazar)
```

Model, Cloud Run container'ının **içine** gömülü çalışır (GCS'den indirilip bellekte tutulur), ayrı bir Vertex AI Online Prediction Endpoint'i **kullanılmıyor** — bilinçli bir maliyet/gecikme kararı: bir endpoint 7/24 ücretlendirilirken, container-içi çıkarım ek ağ gecikmesi ve ek maliyet getirmiyor.

## Proje yapısı

- `edge-simulator/` — Podman ile çalışan, sentetik sensör verisi (bilerek enjekte edilmiş anomalilerle) üreten IoT simülatörü.
- `cloud-run-api/` — FastAPI ingestion servisi: veriyi doğrular, modeli çalıştırır, BigQuery'ye yazar.
- `bigquery/` — Tablo şemaları: `sensor_readings` (partitioned + clustered) ve `acil_bakim_uyarilari`.
- `ml/` — Vertex AI eğitim kodu: `train_isolation_forest.py` (eğitim mantığı), `submit_training_job.py` (Vertex AI'a iş gönderen istemci), `Dockerfile` (eğitim container'ı).
- `scripts/` — Altyapı kurulum/deploy script'leri (`gcloud`/`bq` otomasyonu).
- `cloudbuild.yaml` — CI/CD: GitHub push'unda build + push + Cloud Run deploy.

## Kurulum sırası

### 1) BigQuery tabloları

```bash
bash scripts/setup_bigquery.sh
```

`telemetry.sensor_readings` (timestamp'e göre günlük partition, device_id'ye göre cluster) ve `telemetry.acil_bakim_uyarilari` tablolarını oluşturur.

### 2) Model artifact bucket'ı

```bash
bash scripts/setup_gcs.sh
```

`<proje-id>-pdm-artifacts` adında, eğitilen modelin (`model.joblib`) saklanacağı bir GCS bucket'ı açar.

### 3) Eğitim verisi üret

```bash
source scripts/setup_ml_env.sh
python scripts/generate_historical_data.py --project vestel-pdm-7883 --num-rows 8000
```

BigQuery'ye toplu, ground-truth `is_anomaly` etiketi taşıyan sentetik geçmiş veri yükler (model bunun üzerinde eğitilip değerlendirilecek).

### 4) Modeli Vertex AI'da eğit

Önce eğitim container'ını Artifact Registry'e yükle (bir kere yeterli):

```bash
gcloud artifacts repositories create pdm-training --repository-format=docker --location=europe-west1
gcloud builds submit ml/ --tag europe-west1-docker.pkg.dev/vestel-pdm-7883/pdm-training/isolation-forest-trainer:latest
```

Sonra eğitim işini Vertex AI managed compute'a gönder:

```bash
cd ml && source .venv/bin/activate
python submit_training_job.py --project vestel-pdm-7883 --bucket vestel-pdm-7883-pdm-artifacts
```

Elde edilen sonuçlar (8000 satırlık sentetik veri, %3 enjekte anomali oranı): **Precision: 0.934, Recall: 1.000** — modelin enjekte edilen anomalilerin tamamını yakaladığı, alarmların ~%93'ünün isabetli olduğu bir denge.

### 5) Ingestion API'yi lokalde test et

```bash
cd cloud-run-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

`--host 0.0.0.0` şart: Podman container'ları (`host.containers.internal` üzerinden) servise ancak tüm arayüzlerden dinlerse ulaşabilir, `127.0.0.1` sadece host'un kendi loopback'inden erişilebilir olurdu.

Modeli de lokalde test etmek istersen `MODEL_GCS_PATH` ortam değişkenini ayarla:
```bash
export MODEL_GCS_PATH="gs://vestel-pdm-7883-pdm-artifacts/models/isolation_forest/model.joblib"
```

### 6) Cloud Run'a deploy et

```bash
bash scripts/deploy_cloud_run.sh
```

`cloud-run-api/` klasörünü Cloud Build ile derleyip Cloud Run'da yayınlar, `BQ_DATASET`, `BQ_TABLE`, `BQ_ALERTS_TABLE`, `MODEL_GCS_PATH` ortam değişkenlerini geçer.

> Not: `--allow-unauthenticated` demo/staj amaçlı; servis herkese açık. Üretimde kimlik doğrulama (identity token) eklenmeli.

### 7) Podman ile simülatörü çalıştır

```bash
cd edge-simulator
podman build -t pdm-edge-simulator .
podman run --rm \
  -e INGEST_URL="https://pdm-ingest-api-191805562758.europe-west1.run.app/ingest" \
  -e DEVICE_ID=vestel-motor-001 \
  pdm-edge-simulator
```

Terminalde her okuma `[normal]` ya da `[ANOMALI!]` etiketiyle, Cloud Run'dan dönen HTTP durum koduyla birlikte akar.

## CI/CD

GitHub'a `master` dalına her push, Cloud Build trigger'ını (`v-trigger1`) tetikler: `cloudbuild.yaml`, `cloud-run-api/`'yi derleyip Artifact Registry'e (`pdm-training` deposu) push eder, ardından aynı image'i `pdm-ingest-api` servisine deploy eder. Yani `git push` sonrası birkaç dakika içinde servis otomatik güncellenir — elle `gcloud run deploy` çalıştırmaya gerek yok.

## Maliyet notları

- Cloud Run, BigQuery streaming insert ve Cloud Build'in hepsinin cömert ücretsiz aylık kotaları var; bu projenin trafik hacmiyle pratikte ücretsiz kalıyor.
- Vertex AI eğitim job'ı (`n1-standard-4`, birkaç dakika) kuruşlar mertebesinde bir maliyet.
- Bilinçli olarak **kullanılmayan**: Vertex AI Online Prediction Endpoint (7/24 ücretlendirilir) — bunun yerine model Cloud Run container'ının içine gömülü.
