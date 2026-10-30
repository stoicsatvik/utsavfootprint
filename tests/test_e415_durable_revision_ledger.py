import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from utsav_sensor.models import Observation
from utsav_sensor.revision_store import SQLiteRevisionLedger


def observation(record_id: str, *, status: str = "open") -> Observation:
    past = datetime.now(UTC) - timedelta(hours=1)
    return Observation(
        id=record_id,
        source_type="partner",
        provenance="measured",
        source_id="sensor-1",
        lat=19.076,
        lon=72.8777,
        observed_at=past,
        ingested_at=past,
        status=status,
    )


@pytest.mark.asyncio
async def test_durable_corrections_tombstones_and_restart(tmp_path):
    path = tmp_path / "ledger.db"
    ledger = SQLiteRevisionLedger(path)
    await ledger.start()
    original = observation("site")
    first = await ledger.append(original)
    original.status = "cleaned"  # Must not mutate the persisted first receipt.
    second = await ledger.append(original)
    third = await ledger.append(None, observation_id="site")
    assert [r.sequence for r in (first, second, third)] == [1, 2, 3]
    assert first.observation.status == "open"
    assert second.observation.status == "cleaned"
    if first.recorded_at < second.recorded_at:
        assert (await ledger.hotspots_as_of(
            first.recorded_at, expected_head_sequence=3
        ))[0].status == "open"
    assert await ledger.hotspots_as_of(third.recorded_at, expected_head_sequence=3) == []

    reopened = SQLiteRevisionLedger(path)
    await reopened.start()
    assert [r.sequence for r in await reopened.revisions(expected_head_sequence=3)] == [1, 2, 3]


@pytest.mark.asyncio
async def test_reject_bad_receipts_and_sql_mutation(tmp_path):
    ledger = SQLiteRevisionLedger(tmp_path / "ledger.db")
    await ledger.start()
    with pytest.raises(ValueError):
        await ledger.append(None)
    with pytest.raises(ValueError):
        await ledger.append(observation("site"), observation_id="other")
    future = observation("future")
    future.ingested_at = datetime.now(UTC) + timedelta(days=1)
    with pytest.raises(ValueError):
        await ledger.append(future)
    assert await ledger.revisions(expected_head_sequence=0) == []
    await ledger.append(observation("site"))
    with pytest.raises(ValueError):
        await ledger.revisions(expected_head_sequence=2)
    with pytest.raises(ValueError):
        await ledger.revisions(expected_head_sequence=True)
    with sqlite3.connect(ledger.path) as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM observation_revisions")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE observation_revisions SET observation_id='other'")
    assert len(await ledger.revisions(expected_head_sequence=1)) == 1


@pytest.mark.asyncio
async def test_concurrent_appends_keep_contiguous_sequences(tmp_path):
    ledger = SQLiteRevisionLedger(tmp_path / "ledger.db")
    await ledger.start()
    await asyncio.gather(*(ledger.append(observation(f"site-{i}")) for i in range(12)))
    assert [r.sequence for r in await ledger.revisions(expected_head_sequence=12)] == list(
        range(1, 13)
    )


@pytest.mark.asyncio
async def test_missing_tail_detected_only_with_external_checkpoint(tmp_path):
    ledger = SQLiteRevisionLedger(tmp_path / "ledger.db")
    await ledger.start()
    await ledger.append(observation("site-1"))
    await ledger.append(observation("site-2"))
    with sqlite3.connect(ledger.path) as db:
        db.execute("DROP TRIGGER revision_no_delete")  # Privileged file owner can tamper.
        db.execute("DELETE FROM observation_revisions WHERE sequence=2")
    assert len(await ledger.revisions()) == 1  # A missing suffix is otherwise invisible.
    with pytest.raises(ValueError, match="checkpoint"):
        await ledger.revisions(expected_head_sequence=2)
