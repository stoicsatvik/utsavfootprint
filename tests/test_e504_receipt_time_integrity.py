"""E504: falsify receipt-time integrity under local SQLite tampering.

A separately stored timestamp detects one-field edits, but two-field
coherent rewrites remain possible without an independent trust anchor.
"""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from utsav_sensor.models import Observation
from utsav_sensor.research_receipt import (
    ResearchFirstReceiptStore,
    ResearchReceiptIntegrityError,
)

STAMP = datetime(2026, 11, 2, 9, tzinfo=UTC)


def report():
    return Observation(
        id="e504-receipt",
        source_type="citizen",
        provenance="observed",
        source_id="unverified",
        lat=19.076,
        lon=72.8777,
        observed_at=STAMP,
        ingested_at=STAMP - timedelta(days=1),
        status="open",
    )


def test_payload_only_timestamp_edit_is_rejected_on_get_and_retry(tmp_path):
    path = tmp_path / "receipts.db"
    store = ResearchFirstReceiptStore(path, clock=lambda: STAMP)
    original = store.put(report())
    forged = original.model_copy(
        update={"ingested_at": STAMP - timedelta(days=30)}
    )
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE research_first_receipts SET payload = ? WHERE id = ?",
            (forged.model_dump_json(), original.id),
        )
    with pytest.raises(ResearchReceiptIntegrityError, match="mismatch"):
        store.get(original.id)
    with pytest.raises(ResearchReceiptIntegrityError, match="mismatch"):
        store.put(report())


def test_receipt_column_only_edit_is_rejected(tmp_path):
    path = tmp_path / "receipts.db"
    store = ResearchFirstReceiptStore(path, clock=lambda: STAMP)
    original = store.put(report())
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE research_first_receipts SET receipt_at = ? WHERE id = ?",
            ((STAMP + timedelta(days=1)).isoformat(), original.id),
        )
    with pytest.raises(ResearchReceiptIntegrityError, match="mismatch"):
        store.get(original.id)
    with pytest.raises(ResearchReceiptIntegrityError, match="mismatch"):
        store.put(report())


def test_negative_coherent_time_rewrite_is_not_authenticated(tmp_path):
    """Two-field tampering still bypasses an unauthenticated consistency check."""
    path = tmp_path / "receipts.db"
    store = ResearchFirstReceiptStore(path, clock=lambda: STAMP)
    original = store.put(report())
    forged_time = STAMP - timedelta(days=30)
    forged = original.model_copy(update={"ingested_at": forged_time})
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE research_first_receipts SET payload = ?, receipt_at = ? "
            "WHERE id = ?",
            (forged.model_dump_json(), forged_time.isoformat(), original.id),
        )
    assert store.get(original.id).ingested_at == forged_time
    assert store.put(report()).ingested_at == forged_time


def test_legacy_schema_is_not_silently_backfilled_from_mutable_payload(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE research_first_receipts ("
            "id TEXT PRIMARY KEY, evidence TEXT NOT NULL, payload TEXT NOT NULL)"
        )
    with pytest.raises(ResearchReceiptIntegrityError, match="legacy"):
        ResearchFirstReceiptStore(path, clock=lambda: STAMP)
