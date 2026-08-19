# Vestel Uçtan Buluta Kestirimci Bakım (Predictive Maintenance)

GCP proje: `vestel-pdm-7883` — bölge: `europe-west1`

## Yapı

- `edge-simulator/` — Fedora'da Podman ile çalışacak, sentetik sensör verisi üreten IoT simülatörü.
- `cloud-run-api/` — FastAPI tabanlı ingestion servisi, geleni doğrular ve BigQuery'ye yazar.
- `bigquery/` — Tablo şeması (partitioned + clustered).
- `scripts/` — Altyapı kurulum/deploy script'leri.

Faz 2 (Vertex AI entegrasyonu) henüz eklenmedi; `cloud-run-api/main.py` şu an sadece doğrulayıp BigQuery'ye yazıyor. `is_anomaly` / `anomaly_score` kolonları ileride model tahminiyle doldurulacak.

## 1) BigQuery tablosunu oluştur

```bash
bash scripts/setup_bigquery.sh
```

## 2) Ingestion API'yi lokalde test et

```bash
cd cloud-run-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

`--host 0.0.0.0` şart: Podman container'ları (`host.containers.internal` üzerinden) servise ancak tüm arayüzlerden dinlerse ulaşabilir, `127.0.0.1` sadece host'un kendi loopback'inden erişilebilir olurdu.

ADC zaten kurulu olduğu için (`gcloud auth application-default login`) yerel BigQuery client otomatik çalışır.

Test:
```bash
curl -X POST localhost:8080/ingest -H "Content-Type: application/json" -d '{
  "timestamp": "2026-08-18T12:00:00Z",
  "device_id": "vestel-motor-001",
  "motor_sicakligi": 47.2,
  "titresim_frekansi": 12.8,
  "guc_tuketimi": 225.4
}'
```

## 3) Podman ile simülatörü çalıştır

```bash
cd edge-simulator
podman build -t pdm-simulator .
podman run --rm \
  -e INGEST_URL=http://host.containers.internal:8080/ingest \
  -e DEVICE_ID=vestel-motor-001 \
  pdm-simulator
```

(Lokal API'ye değil, deploy edilmiş Cloud Run servisine göndermek için `INGEST_URL`'i o servisin URL'iyle değiştir.)

## 4) Cloud Run'a deploy et

```bash
bash scripts/deploy_cloud_run.sh
```

Bu, `cloud-run-api/` klasörünü Cloud Build ile derleyip Cloud Run'da yayınlar ve servis URL'ini basar.

> Not: `--allow-unauthenticated` demo/staj amaçlı; servis herkese açık. İleride kimlik doğrulama (identity token) eklenmeli.

## Sıradaki adımlar

- Vertex AI ile anomali tespit modeli (Isolation Forest / AutoML) eğitimi
- Cloud Run'ı Vertex AI Endpoint'e senkron/async (Pub/Sub üzerinden) bağlama
- GitHub + Cloud Build ile CI/CD
