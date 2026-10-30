"""E416: SQLite REPLACE must not bypass append-only revision protection.

All records are synthetic. This tests local SQL integrity, not authenticated
ingestion or resistance to a privileged database owner.
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
        source_id="synthetic-sensor",
        lat=19.076,
        lon=72.8777,
        observed_at=stamp,
        ingested_at=stamp,
        status="open",
    )


@pytest.mark.asyncio
async def test_insert_or_replace_cannot_rewrite_receipt_with_default_pragma(tmp_path):
    ledger = SQLiteRevisionLedger(tmp_path / "revisions.sqlite")
    await ledger.start()
    await ledger.append(_observation("original"))
    with sqlite3.connect(ledger.path) as db:
        assert db.execute("PRAGMA recursive_triggers").fetchone() == (0,)
        before = db.execute(
            "SELECT sequence, recorded_at, observation_id, payload "
            "FROM observation_revisions WHERE sequence=1"
        ).fetchone()
        with pytest.raises(sqlite3.IntegrityError, match="sequence already exists"):
            db.execute(
                "INSERT OR REPLACE INTO observation_revisions "
                "(sequence, recorded_at, observation_id, payload) VALUES (?, ?, ?, ?)",
                (1, datetime.now(UTC).isoformat(), "forged", None),
            )
        after = db.execute(
            "SELECT sequence, recorded_at, observation_id, payload "
            "FROM observation_revisions WHERE sequence=1"
        ).fetchone()
        assert after == before
    assert (await ledger.revisions(expected_head_sequence=1))[0].observation_id == "original"
    # Guard must not block legitimate AUTOINCREMENT inserts.
    assert (await ledger.append(_observation("second"))).sequence == 2


@pytest.mark.asyncio
async def test_start_adds_guard_to_preexisting_ledger(tmp_path):
    ledger = SQLiteRevisionLedger(tmp_path / "legacy.sqlite")
    await ledger.start()
    await ledger.append(_observation("original"))
    with sqlite3.connect(ledger.path) as db:
        db.execute("DROP TRIGGER revision_no_replace")  # Simulate E415 schema.
    await ledger.start()  # Additive migration, no existing receipt rewritten.
    with sqlite3.connect(ledger.path) as db, pytest.raises(
        sqlite3.IntegrityError, match="sequence already exists"
    ):
        db.execute(
            "INSERT OR REPLACE INTO observation_revisions "
            "(sequence, recorded_at, observation_id, payload) VALUES (1, ?, ?, ?)",
            (datetime.now(UTC).isoformat(), "forged", None),
        )
    assert (await ledger.revisions(expected_head_sequence=1))[0].observation_id == "original"
