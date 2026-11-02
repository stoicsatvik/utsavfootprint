"""E496: IDs identify immutable evidence, not mutable update slots."""
import asyncio

import pytest

from utsav_sensor.engine import SensorEngine
from utsav_sensor.errors import ObservationConflictError
from utsav_sensor.models import Observation
from utsav_sensor.store import SQLiteObservationStore


def report(mass: float, *, source: str = "test-source") -> Observation:
    return Observation(
        id="fixed-e496-observation",
        source_type="partner",
        provenance="measured",
        source_id=source,
        lat=19.076,
        lon=72.8777,
        mass_kg_low=mass,
        mass_kg_high=mass,
    )


@pytest.mark.asyncio
async def test_sqlite_duplicate_identical_is_idempotent(tmp_path):
    store = SQLiteObservationStore(tmp_path / "e496.db")
    await store.start()
    item = report(10)
    await store.upsert(item)
    await store.upsert(item.model_copy(deep=True))
    rows = await store.all()
    assert len(rows) == 1 and rows[0] == item


@pytest.mark.asyncio
async def test_sqlite_conflicting_id_preserves_original(tmp_path):
    store = SQLiteObservationStore(tmp_path / "e496.db")
    await store.start()
    original = report(10)
    await store.upsert(original)
    with pytest.raises(ObservationConflictError):
        await store.upsert(report(999))
    assert (await store.all()) == [original]


@pytest.mark.asyncio
async def test_sqlite_conflicting_provenance_source_preserves_original(tmp_path):
    store = SQLiteObservationStore(tmp_path / "e496.db")
    await store.start()
    original = report(10)
    await store.upsert(original)
    with pytest.raises(ObservationConflictError):
        await store.upsert(report(10, source="imposter"))
    assert (await store.all()) == [original]


@pytest.mark.asyncio
async def test_in_memory_engine_conflicting_id_preserves_original():
    engine = SensorEngine()
    original = report(10)
    await engine.ingest(original)
    assert await engine.ingest(original.model_copy(deep=True)) == original
    with pytest.raises(ObservationConflictError):
        await engine.ingest(report(999))
    assert (await engine.observations()) == [original]


@pytest.mark.asyncio
async def test_persistent_engine_conflicting_id_preserves_disk_and_memory(tmp_path):
    store = SQLiteObservationStore(tmp_path / "e496.db")
    engine = SensorEngine(store)
    await engine.start()
    original = report(10)
    await engine.ingest(original)
    with pytest.raises(ObservationConflictError):
        await engine.ingest(report(999))
    assert (await engine.observations()) == [original]
    assert (await store.all()) == [original]


@pytest.mark.asyncio
async def test_concurrent_conflicts_have_single_winner(tmp_path):
    store = SQLiteObservationStore(tmp_path / "e496.db")
    await store.start()
    results = await asyncio.gather(
        store.upsert(report(10)),
        store.upsert(report(20)),
        return_exceptions=True,
    )
    assert sum(isinstance(r, ObservationConflictError) for r in results) == 1
    assert sum(r is None for r in results) == 1
    assert len(await store.all()) == 1
    assert (await store.all())[0].mass_kg_low in (10, 20)
