"""E421: an external checkpoint must bind to the exact historical read.

Synthetic SQLite receipts only. The expected digest is assumed independently
retained; this is not a signature or an authenticated physical-cleanup record.
"""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from utsav_sensor.models import Observation
from utsav_sensor.revision_store import SQLiteRevisionLedger


def _observation(record_id: str, status: str = "open") -> Observation:
    location = {"a": 19.076, "b": 19.096, "c": 19.116}.get(record_id, 19.076)
    past = datetime.now(UTC) - timedelta(hours=1)
    return Observation(
        id=record_id,
        source_type="partner",
        provenance="measured",
        source_id=f"synthetic-{record_id}",
        lat=location,
        lon=72.8777,
        observed_at=past,
        ingested_at=past,
        status=status,
    )


@pytest.mark.asyncio
async def test_split_verification_can_precede_a_valid_but_modified_read(tmp_path):
    ledger = SQLiteRevisionLedger(tmp_path / "revisions.db")
    await ledger.start()
    await ledger.append(_observation("a"))
    trusted = await ledger.checkpoint()

    # E417's two-call pattern checks an earlier state, not the later read.
    await ledger.verify_checkpoint(*trusted)
    forged = _observation("a", "cleaned")
    with sqlite3.connect(ledger.path) as db:
        db.execute("DROP TRIGGER revision_no_update")  # Privileged DB owner.
        db.execute(
            "UPDATE observation_revisions SET payload=? WHERE sequence=1",
            (forged.model_dump_json(),),
        )
    assert (await ledger.revisions())[0].observation.status == "cleaned"

    # E421 binds digest verification and parsing to one read snapshot.
    with pytest.raises(ValueError, match="checkpoint mismatch"):
        await ledger.verified_revisions(*trusted)
    with pytest.raises(ValueError, match="checkpoint mismatch"):
        await ledger.verified_hotspots_as_of(datetime.now(UTC), *trusted)


@pytest.mark.asyncio
async def test_verified_historical_views_match_independent_event_oracle(tmp_path):
    path = tmp_path / "revisions.db"
    ledger = SQLiteRevisionLedger(path)
    await ledger.start()
    actions = [
        ("a", "open"),
        ("b", "open"),
        ("a", "claimed"),
        ("c", "open"),
        ("a", "cleaned"),
        ("b", None),
        ("b", "open"),
        ("c", "verified"),
        ("a", None),
        ("a", "open"),
    ]
    receipts = []
    for record_id, status in actions:
        if status is None:
            receipt = await ledger.append(None, observation_id=record_id)
        else:
            receipt = await ledger.append(_observation(record_id, status))
        receipts.append(receipt)

    trusted = await ledger.checkpoint()
    assert trusted[0] == len(actions)
    for cutoff in sorted({receipt.recorded_at for receipt in receipts}):
        expected = {}
        for receipt in receipts:
            if receipt.recorded_at > cutoff:
                continue
            if receipt.observation is None:
                expected.pop(receipt.observation_id, None)
            else:
                expected[receipt.observation_id] = receipt.observation.status
        hotspots = await ledger.verified_hotspots_as_of(cutoff, *trusted)
        actual = {hotspot.observation_ids[0]: hotspot.status for hotspot in hotspots}
        assert actual == expected

    reopened = SQLiteRevisionLedger(path)
    await reopened.start()
    assert await reopened.checkpoint() == trusted
    assert len(await reopened.verified_revisions(*trusted)) == len(actions)
    await reopened.append(_observation("c", "open"))
    with pytest.raises(ValueError, match="checkpoint mismatch"):
        await reopened.verified_revisions(*trusted)
