from __future__ import annotations

"""NASA Earthdata CMR STAC metadata adapter.

This is remote-sensing scene discovery, not a claim that a satellite can see a flower pile on a
street. It gives the sensor network acquisition timestamps, footprints and assets that a validated
remote-sensing model can consume for large-scale environmental signals.
"""

from datetime import datetime
from typing import Any

from .stac import search_scenes

NASA_CMR_STAC = "https://cmr.earthdata.nasa.gov/stac"


async def search_nasa_scenes(
    bbox: tuple[float, float, float, float],
    start: datetime,
    end: datetime,
    collections: list[str] | None = None,
    provider: str = "LPCLOUD",
    limit: int = 20,
) -> list[dict[str, Any]]:
    endpoint = f"{NASA_CMR_STAC}/{provider}"
    return await search_scenes(endpoint, bbox, start, end, collections, limit)
