"""E429: reject timezone-naive observation timestamps at ingestion and replay."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from utsav_sensor.fusion import build_hotspots_as_of
from utsav_sensor.models import Observation, Provenance, SourceType
from utsav_sensor.store import SQLiteObservationStore


def observation(**overrides):
    return Observation(
        source_type=SourceType.CITIZEN,
        provenance=Provenance.OBSERVED,
        source_id="e429-source",
        lat=19.076,
        lon=72.8777,
        **overrides,
    )


@pytest.mark.parametrize("field", ["observed_at", "ingested_at"])
@pytest.mark.parametrize(
    "naive",
    ["2026-10-30T12:00:00", datetime(2026, 10, 30, 12, 0)],
)
def test_naive_timestamps_rejected(field, naive):
    with pytest.raises(ValidationError):
        observation(**{field: naive})


@pytest.mark.parametrize("field", ["observed_at", "ingested_at"])
def test_replayed_naive_timestamp_rejected(field):
    payload = observation().model_dump(mode="json")
    payload[field] = "2026-10-30T12:00:00"
    with pytest.raises(ValidationError):
        Observation.model_validate(payload)


def test_defaults_are_utc_aware():
    record = observation()
    assert record.observed_at.utcoffset() == timedelta(0)
    assert record.ingested_at.utcoffset() == timedelta(0)


def test_aware_offset_is_canonical_utc_after_sqlite_and_historical_fusion(tmp_path):
    record = observation(
        id="offset-report",
        observed_at="2026-10-30T17:30:00+05:30",
        ingested_at="2026-10-30T12:05:00Z",
    )
    assert record.observed_at == datetime(2026, 10, 30, 12, tzinfo=UTC)
    assert record.observed_at.utcoffset() == timedelta(0)
    store = SQLiteObservationStore(tmp_path / "observations.db")
    store._start_sync()
    store._upsert_sync(record)
    with sqlite3.connect(store.path) as db:
        stored_timestamp = db.execute(
            "SELECT observed_at FROM observations WHERE id = ?", (record.id,)
        ).fetchone()[0]
    assert stored_timestamp == "2026-10-30T12:00:00+00:00"
    loaded = store._all_sync()
    assert len(loaded) == 1
    assert loaded[0].observed_at.utcoffset() == timedelta(0)
    assert loaded[0].ingested_at.utcoffset() == timedelta(0)
    snapshots = build_hotspots_as_of(loaded, datetime(2026, 10, 30, 13, tzinfo=UTC))
    assert len(snapshots) == 1
    assert snapshots[0].observation_count == 1


def test_equivalent_aware_offsets_canonicalize_identically():
    ist = observation(
        id="same",
        observed_at="2026-10-30T17:30:00+05:30",
        ingested_at="2026-10-30T17:35:00+05:30",
    )
    utc = observation(
        id="same",
        observed_at="2026-10-30T12:00:00Z",
        ingested_at="2026-10-30T12:05:00Z",
    )
    assert ist.model_dump_json() == utc.model_dump_json()


def test_sqlite_store_orders_legacy_mixed_offsets_by_instant(tmp_path):
    """A mixed-offset legacy DB must be sorted by instant, not wall-clock text."""
    store = SQLiteObservationStore(tmp_path / "offset-order.db")
    store._start_sync()
    older = observation(
        id="older",
        observed_at="2026-10-30T12:00:00Z",
        ingested_at="2026-10-30T12:05:00Z",
    )
    newer = observation(
        id="newer",
        observed_at="2026-10-30T12:30:00Z",
        ingested_at="2026-10-30T12:35:00Z",
    )
    with sqlite3.connect(store.path) as db:
        for record, original_timestamp in (
            (older, "2026-10-30T17:30:00+05:30"),
            (newer, "2026-10-30T12:30:00+00:00"),
        ):
            payload = record.model_dump(mode="json")
            payload["observed_at"] = original_timestamp
            db.execute(
                "INSERT INTO observations (id, observed_at, ingested_at, payload) "
                "VALUES (?, ?, ?, ?)",
                (record.id, original_timestamp, payload["ingested_at"], json.dumps(payload)),
            )
        # Preserve the original counterexample: SQL TEXT ordering is wrong.
        sql_order = [
            row[0] for row in db.execute(
                "SELECT id FROM observations ORDER BY observed_at DESC"
            )
        ]
    assert sql_order == ["older", "newer"]
    loaded = store._all_sync()
    assert [item.id for item in loaded] == ["newer", "older"]
    assert all(item.observed_at.utcoffset() == timedelta(0) for item in loaded)
    assert loaded[0].observed_at > loaded[1].observed_at
