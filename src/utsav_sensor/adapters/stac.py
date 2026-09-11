from __future__ import annotations

"""STAC scene discovery for satellite/remote-sensing inputs."""

from datetime import datetime
from typing import Any

import httpx


async def search_scenes(
    endpoint: str,
    bbox: tuple[float, float, float, float],
    start: datetime,
    end: datetime,
    collections: list[str] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {
        "bbox": list(bbox),
        "datetime": f"{start.isoformat()}/{end.isoformat()}",
        "limit": limit,
    }
    if collections:
        payload["collections"] = collections

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{endpoint.rstrip('/')}/search", json=payload)
        r.raise_for_status()
        data = r.json()
    scenes = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        scenes.append(
            {
                "id": feature.get("id"),
                "collection": feature.get("collection"),
                "datetime": props.get("datetime"),
                "cloud_cover": props.get("eo:cloud_cover"),
                "bbox": feature.get("bbox"),
                "assets": {k: v.get("href") for k, v in feature.get("assets", {}).items()},
            }
        )
    return scenes
