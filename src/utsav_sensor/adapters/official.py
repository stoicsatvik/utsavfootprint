from __future__ import annotations

"""Minimal official/public data adapters.

Adapters return raw records plus source metadata. Mapping a source-specific field into an Observation
must be explicit; the ingestion layer must never guess that a column is a kilogram measurement.
"""

import csv
import io
from typing import Any

import httpx


async def fetch_json(url: str) -> dict[str, Any] | list[Any]:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()


async def fetch_csv(url: str) -> list[dict[str, str]]:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.text)))
