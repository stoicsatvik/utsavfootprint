from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from .fusion import build_hotspots
from .models import HotspotState, Observation, SourceHealth


class ObservationStore(Protocol):
    async def start(self) -> None: ...
    async def upsert(self, observation: Observation) -> None: ...
    async def all(self) -> list[Observation]: ...


class SensorEngine:
    def __init__(self, store: ObservationStore | None = None) -> None:
        self._observations: dict[str, Observation] = {}
        self._lock = asyncio.Lock()
        self._listeners: set[Callable[[list[HotspotState]], None]] = set()
        self._store = store

    async def start(self) -> None:
        if self._store is None:
            return
        await self._store.start()
        stored = await self._store.all()
        async with self._lock:
            self._observations = {o.id: o for o in stored}

    async def ingest(self, observation: Observation) -> Observation:
        if self._store is not None:
            await self._store.upsert(observation)
        async with self._lock:
            self._observations[observation.id] = observation
        states = await self.hotspots()
        for callback in list(self._listeners):
            callback(states)
        return observation

    async def observations(self) -> list[Observation]:
        async with self._lock:
            return sorted(self._observations.values(), key=lambda x: x.observed_at, reverse=True)

    async def hotspots(self) -> list[HotspotState]:
        obs = await self.observations()
        return sorted(build_hotspots(obs), key=lambda h: (h.confidence, h.unresolved_hours), reverse=True)

    async def source_health(self, stale_after_seconds: int = 900) -> list[SourceHealth]:
        now = datetime.now(UTC)
        grouped: dict[str, list[Observation]] = defaultdict(list)
        for obs in await self.observations():
            grouped[obs.source_id].append(obs)

        health = []
        for source_id, records in grouped.items():
            latest = max(records, key=lambda x: x.ingested_at)
            age = max(0.0, (now - latest.ingested_at).total_seconds())
            health.append(
                SourceHealth(
                    source_id=source_id,
                    source_type=latest.source_type,
                    last_ingested_at=latest.ingested_at,
                    observation_count=len(records),
                    age_seconds=age,
                    state="live" if age <= stale_after_seconds else "stale",
                )
            )
        return sorted(health, key=lambda x: x.last_ingested_at, reverse=True)

    def subscribe(self, callback: Callable[[list[HotspotState]], None]) -> None:
        self._listeners.add(callback)

    def unsubscribe(self, callback: Callable[[list[HotspotState]], None]) -> None:
        self._listeners.discard(callback)
