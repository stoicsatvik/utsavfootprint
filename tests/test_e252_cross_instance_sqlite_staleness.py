"""E252: real SQLite two-engine counterexamples, disposable database only.

A per-instance asyncio lock cannot guarantee cross-instance cache consistency.
Passing tests intentionally preserve the unsafe interleavings; they do not
establish multi-replica safety or real sensor/cleanup authenticity.
"""

import pytest

from utsav_sensor.engine import SensorEngine
from utsav_sensor.models import Observation
from utsav_sensor.store import SQLiteObservationStore


def sample(source: str, oid: str = "shared", status: str = "open") -> Observation:
    return Observation(
        id=oid,
        source_type="partner",
        provenance="measured",
        source_id=source,
        lat=19.076,
        lon=72.8777,
        mass_kg_low=1,
        mass_kg_high=2,
        status=status,
    )


@pytest.mark.asyncio
async def test_same_id_two_engines_disagree_after_sequential_durable_writes(tmp_path):
    path = tmp_path / "two-engines.db"
    a = SensorEngine(SQLiteObservationStore(path))
    b = SensorEngine(SQLiteObservationStore(path))
    await a.start()
    await b.start()

    await a.ingest(sample("first"))
    assert (await a.observations())[0].source_id == "first"
    assert await b.observations() == []  # second instance has no invalidation

    await b.ingest(sample("second", status="cleaned"))
    durable = await SQLiteObservationStore(path).all()
    assert len(durable) == 1
    assert durable[0].source_id == "second"
    assert durable[0].status == "cleaned"
    assert (await a.observations())[0].source_id == "first"
    assert (await a.observations())[0].status == "open"
    assert (await b.observations())[0].source_id == "second"

    # Explicit restart/reload can recover the durable snapshot, but it does
    # not make reads linearizable while another engine is writing.
    await a.start()
    assert (await a.observations())[0].source_id == durable[0].source_id
    assert (await a.observations())[0].status == durable[0].status


@pytest.mark.asyncio
async def test_distinct_ids_leave_each_instance_with_incomplete_hotspot_inputs(tmp_path):
    path = tmp_path / "disjoint-engines.db"
    a = SensorEngine(SQLiteObservationStore(path))
    b = SensorEngine(SQLiteObservationStore(path))
    await a.start()
    await b.start()

    await a.ingest(sample("first", oid="first-id"))
    await b.ingest(sample("second", oid="second-id"))
    durable = await SQLiteObservationStore(path).all()
    assert {o.id for o in durable} == {"first-id", "second-id"}
    assert {o.id for o in await a.observations()} == {"first-id"}
    assert {o.id for o in await b.observations()} == {"second-id"}

    # Re-initialization reads the shared durable state. No cross-instance
    # cache synchronization is present between such explicit reloads.
    await a.start()
    await b.start()
    assert {o.id for o in await a.observations()} == {"first-id", "second-id"}
    assert {o.id for o in await b.observations()} == {"first-id", "second-id"}
