import pytest

from utsav_sensor.models import Observation
from utsav_sensor.store import SQLiteObservationStore


@pytest.mark.asyncio
async def test_sqlite_roundtrip(tmp_path):
    store = SQLiteObservationStore(tmp_path / "sensor.db")
    await store.start()
    item = Observation(
        source_type="partner",
        provenance="measured",
        source_id="scale-1",
        lat=19.076,
        lon=72.8777,
        confidence=0.99,
        mass_kg_low=10,
        mass_kg_high=10.2,
    )
    await store.upsert(item)
    rows = await store.all()
    assert len(rows) == 1
    assert rows[0].id == item.id
    assert rows[0].mass_kg_low == 10
