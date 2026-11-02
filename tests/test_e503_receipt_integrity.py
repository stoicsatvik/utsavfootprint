"""E503: falsify unauthenticated SQLite receipt integrity assumptions.

These tests mutate the research database directly. They are not attacks on the
production API and do not demonstrate cryptographic authentication.
"""

import sqlite3
from datetime import UTC, datetime

import pytest

from utsav_sensor.models import Observation
from utsav_sensor.research_receipt import (
    ResearchFirstReceiptStore,
    ResearchReceiptIntegrityError,
    _evidence_key,
)

STAMP = datetime(2026, 11, 2, 9, tzinfo=UTC)


def report(observation_id="e503-receipt", **changes):
    data = {
        "id": observation_id,
        "source_type": "citizen",
        "provenance": "observed",
        "source_id": "unverified",
        "lat": 19.076,
        "lon": 72.8777,
        "observed_at": STAMP,
        "ingested_at": STAMP,
        "status": "open",
    }
    data.update(changes)
    return Observation(**data)


def test_evidence_only_mutation_fails_closed_on_get_and_retry(tmp_path):
    path = tmp_path / "receipts.db"
    store = ResearchFirstReceiptStore(path, clock=lambda: STAMP)
    first = store.put(report())
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE research_first_receipts SET evidence = ? WHERE id = ?",
            ('{"tampered":true}', first.id),
        )
    with pytest.raises(ResearchReceiptIntegrityError, match="mismatch"):
        store.get(first.id)
    with pytest.raises(ResearchReceiptIntegrityError, match="mismatch"):
        store.put(report())
    # A failed read or retry must not rewrite the corrupted row.
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT evidence FROM research_first_receipts WHERE id = ?",
            (first.id,),
        ).fetchone()[0] == '{"tampered":true}'


def test_payload_id_mutation_fails_closed_on_get_and_retry(tmp_path):
    path = tmp_path / "receipts.db"
    store = ResearchFirstReceiptStore(path, clock=lambda: STAMP)
    first = store.put(report())
    other_id_payload = first.model_copy(update={"id": "other-id"}).model_dump_json()
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE research_first_receipts SET payload = ? WHERE id = ?",
            (other_id_payload, first.id),
        )
    with pytest.raises(ResearchReceiptIntegrityError, match="mismatch"):
        store.get(first.id)
    with pytest.raises(ResearchReceiptIntegrityError, match="mismatch"):
        store.put(report())


def test_negative_coherent_tampering_is_not_authenticated(tmp_path):
    """An attacker able to rewrite BOTH columns can evade this consistency check."""
    path = tmp_path / "receipts.db"
    store = ResearchFirstReceiptStore(path, clock=lambda: STAMP)
    first = store.put(report())
    forged = first.model_copy(update={"source_id": "forged-alias"})
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE research_first_receipts SET evidence = ?, payload = ? WHERE id = ?",
            (_evidence_key(forged), forged.model_dump_json(), first.id),
        )
    assert store.get(first.id).source_id == "forged-alias"
    assert store.put(report(source_id="forged-alias")).source_id == "forged-alias"
    # Consistency is not authenticity; an independent trust anchor is still required.
