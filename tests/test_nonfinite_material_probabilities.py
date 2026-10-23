"""Regression: non-finite material claims must not pass model or legacy audit.

The pre-fix model accepted float("nan") because both range comparisons are false.
A NaN material value can propagate into hotspot output and break strict JSON.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from scripts.audit_legacy_timestamps import audit_database
from utsav_sensor.fusion import build_hotspots
from utsav_sensor.models import Observation
from utsav_sensor.store import SQLiteObservationStore


def valid_observation() -> Observation:
    instant = datetime(2026, 10, 23, 12, tzinfo=UTC)
    return Observation(
        id="nonfinite-row",
        source_type="partner",
        provenance="measured",
        source_id="synthetic-source",
        lat=19.076,
        lon=72.8777,
        observed_at=instant,
        ingested_at=instant,
        materials={"plastic": 0.5},
    )


def test_nonfinite_material_probability_fails_validation():
    payload = valid_observation().model_dump(mode="json")
    payload["materials"]["plastic"] = float("nan")
    with pytest.raises(ValidationError):
        Observation.model_validate(payload)
    with pytest.raises(ValidationError):
        Observation.model_validate_json(json.dumps(payload))


def test_legacy_audit_flags_nan_material_without_modifying_snapshot(tmp_path):
    path = tmp_path / "legacy.db"
    store = SQLiteObservationStore(path)
    store._start_sync()
    payload = valid_observation().model_dump(mode="json")
    payload["materials"]["plastic"] = float("nan")
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO observations (id, observed_at, ingested_at, payload) "
            "VALUES (?, ?, ?, ?)",
            (
                payload["id"],
                payload["observed_at"],
                payload["ingested_at"],
                json.dumps(payload),
            ),
        )
    before = path.read_bytes()
    report, status = audit_database(path)
    assert status == 2
    assert report["affected_rows"] == 1
    assert {"id": "nonfinite-row", "field": "payload", "code": "invalid_observation"} in report["issues"]
    assert path.read_bytes() == before


def test_valid_finite_material_probability_still_fuses():
    observation = valid_observation()
    result = build_hotspots([observation], now=observation.observed_at)
    assert len(result) == 1
    assert result[0].materials == {"plastic": 0.5}
