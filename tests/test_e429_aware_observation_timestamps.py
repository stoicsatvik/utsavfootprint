"""E429: reject timezone-naive observation timestamps at ingestion and replay."""

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


def test_aware_offset_survives_sqlite_and_historical_fusion(tmp_path):
    record = observation(
        observed_at="2026-10-30T17:30:00+05:30",
        ingested_at="2026-10-30T12:05:00Z",
    )
    store = SQLiteObservationStore(tmp_path / "observations.db")
    store._start_sync()
    store._upsert_sync(record)
    loaded = store._all_sync()
    assert len(loaded) == 1
    assert loaded[0].observed_at.utcoffset() == timedelta(hours=5, minutes=30)
    assert loaded[0].ingested_at.utcoffset() == timedelta(0)
    snapshots = build_hotspots_as_of(loaded, datetime(2026, 10, 30, 13, tzinfo=UTC))
    assert len(snapshots) == 1
    assert snapshots[0].observation_count == 1


def test_sqlite_store_orders_offsets_by_instant_not_wall_clock(tmp_path):
    """A later UTC observation must outrank an older +05:30 wall-clock time."""
    store = SQLiteObservationStore(tmp_path / "offset-order.db")
    store._start_sync()
    older = observation(
        id="older",
        observed_at="2026-10-30T17:30:00+05:30",  # 12:00 UTC
        ingested_at="2026-10-30T12:05:00Z",
    )
    newer = observation(
        id="newer",
        observed_at="2026-10-30T12:30:00Z",
        ingested_at="2026-10-30T12:35:00Z",
    )
    store._upsert_sync(older)
    store._upsert_sync(newer)
    assert [item.id for item in store._all_sync()] == ["newer", "older"]
    assert store._all_sync()[0].observed_at > store._all_sync()[1].observed_at
