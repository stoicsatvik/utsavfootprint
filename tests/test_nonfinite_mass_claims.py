"""E187: non-finite mass claims must fail before fusion and legacy audit.

Pydantic's ge=0 permits positive infinity without an explicit finite constraint.
The prior NaN material fix did not cover mass fields.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from utsav_sensor.fusion import build_hotspots
from utsav_sensor.models import Observation
from utsav_sensor.store import SQLiteObservationStore

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_legacy_timestamps.py"
NOW = datetime(2026, 10, 24, 0, tzinfo=UTC)


def payload() -> dict:
    return Observation(
        id="mass-row",
        source_type="partner",
        provenance="measured",
        source_id="mass-sensor",
        lat=19.076,
        lon=72.8777,
        observed_at=NOW,
        ingested_at=NOW,
        mass_kg_low=100.0,
        mass_kg_high=200.0,
    ).model_dump(mode="json")


@pytest.mark.parametrize("field", ["mass_kg_low", "mass_kg_high"])
def test_positive_infinite_mass_is_rejected_by_model_and_json(field):
    data = payload()
    data[field] = float("inf")
    with pytest.raises(ValidationError):
        Observation.model_validate(data)
    with pytest.raises(ValidationError):
        Observation.model_validate_json(json.dumps(data))


def test_legacy_audit_detects_infinite_mass_without_mutating_database(tmp_path):
    db_path = tmp_path / "historical.db"
    store = SQLiteObservationStore(db_path)
    store._start_sync()
    data = payload()
    data["mass_kg_high"] = float("inf")
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO observations (id, observed_at, ingested_at, payload) "
            "VALUES (?, ?, ?, ?)",
            ("mass-row", data["observed_at"], data["ingested_at"], json.dumps(data)),
        )
    before = db_path.read_bytes()
    completed = subprocess.run(
        [sys.executable, str(AUDIT), str(db_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(completed.stdout)
    assert completed.returncode == 2
    assert report["affected_rows"] == 1
    assert {"id": "mass-row", "field": "payload", "code": "invalid_observation"} in report["issues"]
    assert db_path.read_bytes() == before


def test_finite_mass_interval_still_fuses():
    observation = Observation.model_validate(payload())
    hotspots = build_hotspots([observation], now=NOW)
    assert len(hotspots) == 1
    assert hotspots[0].mass_kg_low == 100.0
    assert hotspots[0].mass_kg_high == 200.0
