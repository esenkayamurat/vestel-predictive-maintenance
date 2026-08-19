import os
import random
import time
from datetime import datetime, timezone

import requests

INGEST_URL = os.environ.get("INGEST_URL", "http://localhost:8080/ingest")
DEVICE_ID = os.environ.get("DEVICE_ID", "vestel-motor-001")
INTERVAL_SECONDS = float(os.environ.get("INTERVAL_SECONDS", "1"))
ANOMALY_PROBABILITY = float(os.environ.get("ANOMALY_PROBABILITY", "0.03"))

BASE_TEMP = 45.0
BASE_VIBRATION = 12.0
BASE_POWER = 220.0


def generate_reading(anomaly: bool) -> dict:
    if anomaly:
        motor_sicakligi = BASE_TEMP + random.uniform(25, 45)
        titresim_frekansi = BASE_VIBRATION + random.uniform(15, 30)
        guc_tuketimi = BASE_POWER + random.uniform(80, 150)
    else:
        motor_sicakligi = BASE_TEMP + random.gauss(0, 2)
        titresim_frekansi = BASE_VIBRATION + random.gauss(0, 1)
        guc_tuketimi = BASE_POWER + random.gauss(0, 8)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "device_id": DEVICE_ID,
        "motor_sicakligi": round(motor_sicakligi, 2),
        "titresim_frekansi": round(titresim_frekansi, 2),
        "guc_tuketimi": round(guc_tuketimi, 2),
    }


def main():
    print(f"IoT simulator baslatildi -> {INGEST_URL} (device: {DEVICE_ID})")
    while True:
        anomaly = random.random() < ANOMALY_PROBABILITY
        reading = generate_reading(anomaly)
        try:
            resp = requests.post(INGEST_URL, json=reading, timeout=5)
            tag = "ANOMALI!" if anomaly else "normal"
            print(f"[{tag}] {reading} -> {resp.status_code}")
        except requests.RequestException as exc:
            print(f"Gonderim hatasi: {exc}")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
