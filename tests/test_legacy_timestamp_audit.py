"""E176: legacy SQLite timestamp audit must be read-only and explicit."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from utsav_sensor.models import Observation
from utsav_sensor.store import SQLiteObservationStore

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_legacy_timestamps.py"
INSTANT = datetime(2026, 10, 23, 12, tzinfo=UTC)


def add_record(db: Path, *, row_id="report-1", observed=None, ingested=None,
               payload_observed=None, payload_ingested=None, payload=None):
    base = Observation(
        id=row_id, source_type="partner", provenance="measured", source_id="sensor-1",
        lat=19.076, lon=72.8777, observed_at=INSTANT, ingested_at=INSTANT,
    )
    data = json.loads(base.model_dump_json())
    if payload_observed is not None:
        data["observed_at"] = payload_observed
    if payload_ingested is not None:
        data["ingested_at"] = payload_ingested
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO observations(id, observed_at, ingested_at, payload) VALUES(?, ?, ?, ?)",
            (
                row_id,
                observed if observed is not None else INSTANT.isoformat(),
                ingested if ingested is not None else INSTANT.isoformat(),
                payload if payload is not None else json.dumps(data),
            ),
        )


def run_audit(db: Path):
    completed = subprocess.run(
        [sys.executable, str(AUDIT), str(db)], capture_output=True, text=True,
        cwd=ROOT, check=False,
    )
    return completed, json.loads(completed.stdout)


@pytest.mark.asyncio
async def test_audit_accepts_equivalent_aware_offsets_without_writing(tmp_path):
    db = tmp_path / "sensor.db"
    await SQLiteObservationStore(db).start()
    offset = INSTANT.astimezone(timezone(timedelta(hours=5, minutes=30))).isoformat()
    add_record(db, observed=offset, payload_observed=INSTANT.isoformat())
    before = db.read_bytes()
    result, report = run_audit(db)
    assert result.returncode == 0, result.stderr
    assert report["total_rows"] == 1
    assert report["affected_rows"] == 0
    assert report["issues"] == []
    assert db.read_bytes() == before


@pytest.mark.asyncio
async def test_audit_finds_naive_legacy_payload_and_column_without_rewriting(tmp_path):
    db = tmp_path / "sensor.db"
    await SQLiteObservationStore(db).start()
    naive = INSTANT.replace(tzinfo=None).isoformat()
    add_record(db, observed=naive, payload_observed=naive)
    before = db.read_bytes()
    result, report = run_audit(db)
    assert result.returncode == 2
    assert report["affected_rows"] == 1
    assert {(issue["field"], issue["code"]) for issue in report["issues"]} == {
        ("observed_at", "naive_timestamp"),
        ("payload.observed_at", "naive_timestamp"),
    }
    assert all(issue["id"] == "report-1" for issue in report["issues"])
    assert db.read_bytes() == before
    with pytest.raises(ValidationError, match="timezone"):
        Observation.model_validate_json(
            sqlite3.connect(db).execute("SELECT payload FROM observations").fetchone()[0]
        )


@pytest.mark.asyncio
async def test_audit_detects_column_payload_instant_disagreement(tmp_path):
    db = tmp_path / "sensor.db"
    await SQLiteObservationStore(db).start()
    add_record(db, observed=(INSTANT + timedelta(hours=1)).isoformat())
    result, report = run_audit(db)
    assert result.returncode == 2
    assert report["affected_rows"] == 1
    assert ("observed_at", "instant_mismatch") in {
        (issue["field"], issue["code"]) for issue in report["issues"]
    }


@pytest.mark.asyncio
async def test_audit_reports_corrupt_payload_without_exposing_contents(tmp_path):
    db = tmp_path / "sensor.db"
    await SQLiteObservationStore(db).start()
    add_record(db, payload="{not-json")
    result, report = run_audit(db)
    assert result.returncode == 2
    assert report["affected_rows"] == 1
    assert report["issues"] == [
        {"id": "report-1", "field": "payload", "code": "invalid_json"}
    ]
    assert "{not-json" not in result.stdout


def test_audit_missing_database_does_not_create_one(tmp_path):
    db = tmp_path / "missing.db"
    result, report = run_audit(db)
    assert result.returncode == 1
    assert report["error"] == "database_unavailable"
    assert not db.exists()
