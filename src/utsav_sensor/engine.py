from __future__ import annotations

import asyncio
from collections.abc import Callable

from .fusion import build_hotspots
from .models import HotspotState, Observation


class SensorEngine:
    """In-process reference engine.

    It deliberately keeps persistence behind a tiny interface so Supabase/Postgres/Kafka can be
    added without rewriting the sensor math. This reference implementation is runnable immediately.
    """

    def __init__(self) -> None:
        self._observations: dict[str, Observation] = {}
        self._lock = asyncio.Lock()
        self._listeners: set[Callable[[list[HotspotState]], None]] = set()

    async def ingest(self, observation: Observation) -> Observation:
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

    def subscribe(self, callback: Callable[[list[HotspotState]], None]) -> None:
        self._listeners.add(callback)

    def unsubscribe(self, callback: Callable[[list[HotspotState]], None]) -> None:
        self._listeners.discard(callback)
