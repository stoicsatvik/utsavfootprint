#!/usr/bin/env python3
from __future__ import annotations

import random
import time
from datetime import UTC, datetime

import httpx

API = "http://127.0.0.1:8000/v1/observations"
CENTRES = [
    (19.0178, 72.8478, "dadar"),
    (18.9440, 72.8230, "girgaon"),
    (19.1120, 72.8620, "andheri"),
]

for i in range(18):
    lat, lon, area = random.choice(CENTRES)
    low = random.uniform(8, 35)
    payload = {
        "source_type": "citizen",
        "provenance": "observed",
        "source_id": f"demo-user-{i % 9}",
        "lat": lat + random.uniform(-0.00025, 0.00025),
        "lon": lon + random.uniform(-0.00025, 0.00025),
        "observed_at": datetime.now(UTC).isoformat(),
        "confidence": random.uniform(0.55, 0.9),
        "media_quality": random.uniform(0.6, 1.0),
        "materials": {"flowers": random.uniform(0.5, 1), "plastic": random.uniform(0.1, 0.7)},
        "mass_kg_low": low,
        "mass_kg_high": low * random.uniform(1.2, 1.8),
        "status": "open",
        "metadata": {"demo": True, "area": area},
    }
    r = httpx.post(API, json=payload, timeout=10)
    r.raise_for_status()
    print(r.json()["id"])
    time.sleep(0.15)
