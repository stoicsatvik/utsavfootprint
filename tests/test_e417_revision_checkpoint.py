"""E417: an independently retained digest detects same-length SQLite rewrites.

All observations are synthetic. The checkpoint is NOT a signature or a
tamper-proof local record; tests model an external trusted copy explicitly.
"""
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from utsav_sensor.models import Observation
from utsav_sensor.revision_store import SQLiteRevisionLedger


def _observation(record_id: str) -> Observation:
    stamp = datetime.now(UTC) - timedelta(hours=1)
    return Observation(
        id=record_id,
        source_type="partner",
        provenance="measured",
        source_id="synthetic-e417",
        lat=19.076,
        lon=72.8777,
        observed_at=stamp,
        ingested_at=stamp,
        status="open",
    )


@pytest.mark.asyncio
async def test_checkpoint_stable_across_restart_and_append(tmp_path):
    path = tmp_path / "revision.db"
    ledger = SQLiteRevisionLedger(path)
    await ledger.start()
    empty = await ledger.checkpoint()
    assert empty[0] == 0 and len(empty[1]) == 64
    await ledger.verify_checkpoint(*empty)
    await ledger.append(_observation("first"))
    frozen = await ledger.checkpoint()  # Simulate trusted off-database retention.
    assert frozen[0] == 1 and frozen != empty
    reopened = SQLiteRevisionLedger(path)
    await reopened.start()
    assert await reopened.checkpoint() == frozen
    await reopened.verify_checkpoint(*frozen)
    await reopened.append(_observation("second"))
    with pytest.raises(ValueError, match="checkpoint mismatch"):
        await reopened.verify_checkpoint(*frozen)


@pytest.mark.asyncio
async def test_external_digest_detects_equal_length_payload_rewrite(tmp_path):
    ledger = SQLiteRevisionLedger(tmp_path / "revision.db")
    await ledger.start()
    await ledger.append(_observation("first"))
    trusted_head, trusted_hash = await ledger.checkpoint()
    with sqlite3.connect(ledger.path) as db:
        db.execute("DROP TRIGGER revision_no_update")  # Privileged DB owner.
        db.execute(
            "UPDATE observation_revisions SET observation_id='other' WHERE sequence=1"
        )
    assert (await ledger.checkpoint())[0] == trusted_head
    assert (await ledger.checkpoint())[1] != trusted_hash
    with pytest.raises(ValueError, match="checkpoint mismatch"):
        await ledger.verify_checkpoint(trusted_head, trusted_hash)


@pytest.mark.asyncio
async def test_external_checkpoint_detects_missing_tail_and_gap(tmp_path):
    ledger = SQLiteRevisionLedger(tmp_path / "revision.db")
    await ledger.start()
    await ledger.append(_observation("first"))
    await ledger.append(_observation("second"))
    trusted = await ledger.checkpoint()
    with sqlite3.connect(ledger.path) as db:
        db.execute("DROP TRIGGER revision_no_delete")  # Privileged DB owner.
        db.execute("DELETE FROM observation_revisions WHERE sequence=2")
    with pytest.raises(ValueError, match="checkpoint mismatch"):
        await ledger.verify_checkpoint(*trusted)
    with sqlite3.connect(ledger.path) as db:
        db.execute("DELETE FROM observation_revisions WHERE sequence=1")
        db.execute(
            "INSERT INTO observation_revisions(sequence, recorded_at, observation_id, payload) "
            "VALUES (2, ?, 'synthetic', NULL)",
            (datetime.now(UTC).isoformat(),),
        )
    with pytest.raises(ValueError, match="sequence gap"):
        await ledger.checkpoint()


@pytest.mark.asyncio
async def test_checkpoint_rejects_invalid_trusted_inputs(tmp_path):
    ledger = SQLiteRevisionLedger(tmp_path / "revision.db")
    await ledger.start()
    for sequence, digest in [(True, "0" * 64), (-1, "0" * 64), (0, "not-a-digest"), (0, "A" * 64)]:
        with pytest.raises(ValueError, match="invalid external"):
            await ledger.verify_checkpoint(sequence, digest)
