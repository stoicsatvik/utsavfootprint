"""E280: cross-engine stale same-ID replay after a newer cleanup event.

All records are deliberately synthetic. Read-through is a visibility guarantee,
not a causal-revision or physical-cleanup authenticity guarantee.
"""
from datetime import UTC, datetime, timedelta
import sqlite3

import pytest

from utsav_sensor.engine import SensorEngine
from utsav_sensor.models import Observation
from utsav_sensor.store import SQLiteObservationStore


T0 = datetime(2026, 10, 25, 12, tzinfo=UTC)


def event(status: str, when: datetime, *, oid: str = "shared") -> Observation:
    return Observation(
        id=oid, source_type="partner", provenance="measured",
        source_id="synthetic-partner", lat=19.076, lon=72.8777,
        observed_at=when, ingested_at=when, mass_kg_low=1,
        mass_kg_high=2, status=status,
    )


@pytest.mark.asyncio
async def test_old_open_payload_can_replace_newer_cleaned_commit(tmp_path):
    path = tmp_path / "stale-replay.db"
    a, b = (SensorEngine(SQLiteObservationStore(path)) for _ in range(2))
    await a.start()
    await b.start()
    old_open = event("open", T0)
    newer_cleaned = event("cleaned", T0 + timedelta(hours=1))

    await a.ingest(old_open)
    await b.ingest(newer_cleaned)
    assert (await a.observations())[0].status == "cleaned"
    assert (await b.observations())[0].status == "cleaned"

    # A retries an older observation with the same identifier after B commits.
    await a.ingest(old_open)
    durable = await SQLiteObservationStore(path).all()
    assert len(durable) == 1
    assert durable[0].status == "open"
    assert durable[0].observed_at < newer_cleaned.observed_at
    assert (await b.observations())[0].status == "open"
    assert (await a.hotspots())[0].status == "open"


@pytest.mark.asyncio
async def test_distinct_event_ids_preserve_history_instead_of_overwriting(tmp_path):
    path = tmp_path / "append-events.db"
    engine = SensorEngine(SQLiteObservationStore(path))
    await engine.start()
    await engine.ingest(event("open", T0, oid="old"))
    await engine.ingest(event("cleaned", T0 + timedelta(hours=1), oid="new"))
    durable = await SQLiteObservationStore(path).all()
    assert len(durable) == 2
    assert {x.status for x in durable} == {"open", "cleaned"}


@pytest.mark.asyncio
async def test_sqlite_compare_and_swap_reference_rejects_stale_writer(tmp_path):
    path = tmp_path / "cas-reference.db"
    engine = SensorEngine(SQLiteObservationStore(path))
    await engine.start()
    old_open = event("open", T0)
    cleaned = event("cleaned", T0 + timedelta(hours=1))
    await engine.ingest(old_open)
    await engine.ingest(cleaned)
    # An atomic expected-revision predicate can reject a stale update.
    # This control uses payload equality only in disposable SQL, NOT an
    # authenticated server-owned revision or production API.
    with sqlite3.connect(path) as db:
        cursor = db.execute(
            "UPDATE observations SET payload=? WHERE id=? AND payload=?",
            (old_open.model_dump_json(), old_open.id, old_open.model_dump_json()),
        )
        assert cursor.rowcount == 0
    assert (await engine.observations())[0].status == "cleaned"
