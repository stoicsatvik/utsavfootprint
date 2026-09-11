from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

from .models import Observation


class SQLiteObservationStore:
    """Durable local-first observation log.

    One JSON record per observation keeps schema evolution simple. Production deployments can swap
    this adapter for Postgres/Supabase while preserving SensorEngine's interface.
    """

    def __init__(self, path: str | Path = "data/utsav.db") -> None:
        self.path = Path(path)

    async def start(self) -> None:
        await asyncio.to_thread(self._start_sync)

    def _start_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    id TEXT PRIMARY KEY,
                    observed_at TEXT NOT NULL,
                    ingested_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_observed_at ON observations(observed_at)")

    async def upsert(self, observation: Observation) -> None:
        await asyncio.to_thread(self._upsert_sync, observation)

    def _upsert_sync(self, observation: Observation) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute(
                """
                INSERT INTO observations(id, observed_at, ingested_at, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    observed_at=excluded.observed_at,
                    ingested_at=excluded.ingested_at,
                    payload=excluded.payload
                """,
                (
                    observation.id,
                    observation.observed_at.isoformat(),
                    observation.ingested_at.isoformat(),
                    observation.model_dump_json(),
                ),
            )

    async def all(self) -> list[Observation]:
        return await asyncio.to_thread(self._all_sync)

    def _all_sync(self) -> list[Observation]:
        if not self.path.exists():
            return []
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT payload FROM observations ORDER BY observed_at DESC").fetchall()
        return [Observation.model_validate_json(row[0]) for row in rows]
