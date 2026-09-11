from __future__ import annotations

"""Authorised CCTV persistent-change candidate generator.

This module intentionally does NOT discover public cameras, bypass credentials, identify people,
or claim a persistent blob is definitely waste. It converts a camera the operator is authorised to
use into low-confidence *candidate* observations that require corroboration.
"""

import argparse
import time
from datetime import datetime, timezone

import httpx


def run(rtsp_url: str, api_url: str, source_id: str, lat: float, lon: float, persist_s: int = 120):
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise SystemExit("Install with: pip install -e '.[cctv]'") from exc

    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        raise SystemExit("Could not open the explicitly supplied camera stream")

    subtractor = cv2.createBackgroundSubtractorMOG2(history=800, varThreshold=32, detectShadows=False)
    first_seen: float | None = None
    last_emit = 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(1)
            continue
        # Process a small grayscale frame in memory. No frame is persisted or uploaded.
        h, w = frame.shape[:2]
        scale = min(1.0, 640 / max(w, 1))
        small = cv2.resize(frame, (int(w * scale), int(h * scale)))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        mask = subtractor.apply(gray)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        changed_fraction = float((mask > 0).mean())

        significant = 0.01 < changed_fraction < 0.35
        now = time.time()
        if significant:
            first_seen = first_seen or now
        else:
            first_seen = None

        if first_seen and now - first_seen >= persist_s and now - last_emit >= persist_s:
            payload = {
                "source_type": "cctv",
                "provenance": "modelled",
                "source_id": source_id,
                "lat": lat,
                "lon": lon,
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "confidence": min(0.55, 0.25 + changed_fraction),
                "media_quality": 0.8,
                "materials": {},
                "status": "candidate",
                "metadata": {
                    "detector": "persistent_background_change_v1",
                    "changed_fraction": changed_fraction,
                    "frames_retained": False,
                    "requires_corroboration": True,
                },
            }
            httpx.post(f"{api_url.rstrip('/')}/v1/observations", json=payload, timeout=10).raise_for_status()
            last_emit = now


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rtsp", required=True, help="RTSP/HTTP camera URL you are authorised to use")
    p.add_argument("--api", default="http://127.0.0.1:8000")
    p.add_argument("--source-id", required=True)
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--persist-seconds", type=int, default=120)
    args = p.parse_args()
    run(args.rtsp, args.api, args.source_id, args.lat, args.lon, args.persist_seconds)


if __name__ == "__main__":
    main()
