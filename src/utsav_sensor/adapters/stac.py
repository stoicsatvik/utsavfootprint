from __future__ import annotations

"""STAC scene discovery for satellite/remote-sensing inputs.

This discovers imagery only. It does not magically convert a 10-30 m satellite pixel into a street
waste measurement. Downstream models may emit observations if they can justify that inference.
"""

from datetime import datetime
from typing import Any

import httpx


async def search_scenes(
    endpoint: str,
    bbox: tuple[float, float, float, float],
    start: datetime,
    end: datetime,
    collections: list[str],
    limit: int = 20,
) -> list[dict[str, Any]]:
    payload = {
        "bbox": list(bbox),
        "datetime": f"{start.isoformat()}/{end.isoformat()}",
        "collections": collections,
        "limit": limit,
    }
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
