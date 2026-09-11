#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import time
from pathlib import Path

from utsav_sensor.adapters.cctv import run


def camera_worker(camera: dict, api: str) -> None:
    env_name = camera["url_env"]
    stream_url = os.environ.get(env_name)
    if not stream_url:
        raise RuntimeError(f"missing camera URL environment variable: {env_name}")
    run(
        stream_url,
        api,
        camera["source_id"],
        float(camera["lat"]),
        float(camera["lon"]),
        int(camera.get("persist_seconds", 120)),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an authorised CCTV edge-agent fleet")
    parser.add_argument("config", type=Path)
    args = parser.parse_args()

    config = json.loads(args.config.read_text())
    api = config.get("api", "http://127.0.0.1:8000")
    processes: dict[str, mp.Process] = {}

    while True:
        for camera in config.get("cameras", []):
            source_id = camera["source_id"]
            process = processes.get(source_id)
            if process is None or not process.is_alive():
                process = mp.Process(target=camera_worker, args=(camera, api), daemon=True)
                process.start()
                processes[source_id] = process
        time.sleep(5)


if __name__ == "__main__":
    main()
