"""E177: detect legacy payloads that pass timestamp checks but violate load integrity."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from utsav_sensor.models import Observation
from utsav_sensor.store import SQLiteObservationStore

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_legacy_timestamps.py"
NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)


def fixture_payload() -> dict:
    return json.loads(
        Observation(
            id="row-1",
            source_type="partner",
            provenance="measured",
            source_id="sensor-1",
            lat=19.076,
            lon=72.8777,
            observed_at=NOW,
            ingested_at=NOW,
        ).model_dump_json()
    )


def check_payload(tmp_path: Path, payload: dict):
    db_path = tmp_path / "legacy.db"
    store = SQLiteObservationStore(db_path)
    store._start_sync()
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO observations (id, observed_at, ingested_at, payload) "
            "VALUES (?, ?, ?, ?)",
            ("row-1", NOW.isoformat(), NOW.isoformat(), json.dumps(payload)),
        )
    before = db_path.read_bytes()
    completed = subprocess.run(
        [sys.executable, str(AUDIT), str(db_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    report = json.loads(completed.stdout)
    assert db_path.read_bytes() == before
    assert report["total_rows"] == 1
    assert report["affected_rows"] == 1
    assert completed.returncode == 2
    return report, completed, store


def test_invalid_schema_with_valid_timestamps_is_not_a_clean_audit(tmp_path):
    payload = fixture_payload()
    payload["lat"] = 999.0
    report, completed, store = check_payload(tmp_path, payload)
    assert {"id": "row-1", "field": "payload", "code": "invalid_observation"} in report["issues"]
    assert "999" not in completed.stdout
    with pytest.raises(ValidationError):
        store._all_sync()


def test_payload_identity_mismatch_is_flagged(tmp_path):
    payload = fixture_payload()
    payload["id"] = "other-row"
    report, _, _ = check_payload(tmp_path, payload)
    assert {"id": "row-1", "field": "payload.id", "code": "id_mismatch"} in report["issues"]


def test_missing_payload_identity_is_flagged_despite_model_default(tmp_path):
    payload = fixture_payload()
    del payload["id"]
    report, _, _ = check_payload(tmp_path, payload)
    assert {"id": "row-1", "field": "payload.id", "code": "missing_id"} in report["issues"]
