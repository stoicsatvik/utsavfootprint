"""E235: deterministic persisted-state/cache ordering under concurrent operations.

These are disposable in-memory stores, not production sensor observations.
The tests intentionally force storage and task scheduling to disagree.
"""

import asyncio

import pytest

from utsav_sensor.engine import SensorEngine
from utsav_sensor.models import Observation


def observation(source: str, oid: str = "shared") -> Observation:
    return Observation(
        id=oid,
        source_type="partner",
        provenance="measured",
        source_id=source,
        lat=19.076,
        lon=72.8777,
        mass_kg_low=1,
        mass_kg_high=2,
    )


class DelayedWriteStore:
    def __init__(self) -> None:
        self.persisted: dict[str, Observation] = {}
        self.first_written = asyncio.Event()
        self.release_first = asyncio.Event()
        self.second_written = asyncio.Event()

    async def start(self) -> None:
        pass

    async def all(self) -> list[Observation]:
        return list(self.persisted.values())

    async def upsert(self, item: Observation) -> None:
        self.persisted[item.id] = item
        if item.source_id == "first":
            self.first_written.set()
            await self.release_first.wait()
        else:
            self.second_written.set()


class DelayedSnapshotStore:
    def __init__(self) -> None:
        self.persisted: dict[str, Observation] = {}
        self.snapshot_taken = asyncio.Event()
        self.release_snapshot = asyncio.Event()
        self.write_done = asyncio.Event()

    async def start(self) -> None:
        pass

    async def all(self) -> list[Observation]:
        snapshot = list(self.persisted.values())
        self.snapshot_taken.set()
        await self.release_snapshot.wait()
        return snapshot

    async def upsert(self, item: Observation) -> None:
        self.persisted[item.id] = item
        self.write_done.set()


@pytest.mark.asyncio
async def test_concurrent_upserts_cannot_diverge_from_durable_state() -> None:
    store = DelayedWriteStore()
    engine = SensorEngine(store)
    first = asyncio.create_task(engine.ingest(observation("first")))
    await asyncio.wait_for(store.first_written.wait(), timeout=2)
    second = asyncio.create_task(engine.ingest(observation("second")))

    # Pre-fix: second writes and publishes while first remains in storage.
    # Post-fix: second waits for the engine's storage/cache transaction lock.
    try:
        await asyncio.wait_for(store.second_written.wait(), timeout=0.05)
    except TimeoutError:
        pass
    finally:
        store.release_first.set()

    await asyncio.wait_for(asyncio.gather(first, second), timeout=2)
    cached = await engine.observations()
    assert len(cached) == 1
    assert cached[0].source_id == store.persisted["shared"].source_id


@pytest.mark.asyncio
async def test_start_snapshot_cannot_erase_concurrent_ingest() -> None:
    store = DelayedSnapshotStore()
    engine = SensorEngine(store)
    loading = asyncio.create_task(engine.start())
    await asyncio.wait_for(store.snapshot_taken.wait(), timeout=2)
    writing = asyncio.create_task(engine.ingest(observation("new", oid="new-id")))

    # Pre-fix: ingestion completes, then the older load snapshot replaces it.
    # Post-fix: the load holds the same lock as durable ingestion.
    try:
        await asyncio.wait_for(store.write_done.wait(), timeout=0.05)
    except TimeoutError:
        pass
    finally:
        store.release_snapshot.set()

    await asyncio.wait_for(asyncio.gather(loading, writing), timeout=2)
    cached = await engine.observations()
    assert {o.id for o in cached} == set(store.persisted)
