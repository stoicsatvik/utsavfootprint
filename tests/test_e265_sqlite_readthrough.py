"""E265: committed SQLite read-through, including an independent writer process.

All observations are synthetic and databases are disposable. A completed
SQLite commit must be visible to the next read; a corrupt committed payload
must fail closed instead of returning a stale engine-local snapshot.
"""
import asyncio
import sqlite3
import sys

import pytest

from utsav_sensor.engine import SensorEngine
from utsav_sensor.models import Observation
from utsav_sensor.store import SQLiteObservationStore


def sample(source: str, status: str = "open") -> Observation:
    return Observation(
        id="shared",
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
async def test_independent_python_process_commit_is_visible_without_restart(tmp_path):
    path = tmp_path / "external-writer.db"
    engine = SensorEngine(SQLiteObservationStore(path))
    await engine.start()
    await engine.ingest(sample("engine", "open"))

    updated = sample("independent-process", "cleaned")
    writer = """
import sqlite3, sys
with sqlite3.connect(sys.argv[1]) as db:
    db.execute(
        'UPDATE observations SET observed_at=?, ingested_at=?, payload=? WHERE id=?',
        (sys.argv[2], sys.argv[3], sys.argv[4], 'shared'),
    )
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        writer,
        str(path),
        updated.observed_at.isoformat(),
        updated.ingested_at.isoformat(),
        updated.model_dump_json(),
    )
    assert await asyncio.wait_for(process.wait(), timeout=10) == 0
    records = await engine.observations()
    assert len(records) == 1
    assert records[0].source_id == "independent-process"
    assert records[0].status == "cleaned"
    assert (await engine.hotspots())[0].status == "cleaned"


@pytest.mark.asyncio
async def test_corrupt_durable_snapshot_never_falls_back_to_old_cache(tmp_path):
    path = tmp_path / "corrupt-writer.db"
    engine = SensorEngine(SQLiteObservationStore(path))
    await engine.start()
    await engine.ingest(sample("before-corruption"))
    assert (await engine.observations())[0].source_id == "before-corruption"

    with sqlite3.connect(path) as db:
        db.execute("UPDATE observations SET payload=? WHERE id=?", ("{invalid-json", "shared"))

    with pytest.raises(ValueError):
        await engine.observations()
    with pytest.raises(ValueError):
        await engine.hotspots()
