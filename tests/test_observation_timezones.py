"""E175: observation timestamps must have explicit timezones.

Naive wall-clock values have no globally defined instant. Reject them rather
than silently assuming the server's local timezone. Normalize aware offsets
to UTC so fusion and persistence compare identical instants consistently.
"""
from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from utsav_sensor.fusion import build_hotspots
from utsav_sensor.models import Observation

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
IST = timezone(timedelta(hours=5, minutes=30))


def report(**overrides) -> Observation:
    values = {
        "id": "offset-report",
        "source_type": "partner",
        "provenance": "measured",
        "source_id": "sensor-1",
        "lat": 19.076,
        "lon": 72.8777,
        "observed_at": NOW - timedelta(hours=1),
        "ingested_at": NOW,
        "confidence": 0.9,
    }
    values.update(overrides)
    return Observation(**values)


def test_naive_observation_time_is_rejected_before_fusion():
    with pytest.raises(ValidationError, match="timezone"):
        report(observed_at=NOW.replace(tzinfo=None))


def test_naive_ingestion_time_is_rejected_before_storage():
    with pytest.raises(ValidationError, match="timezone"):
        report(ingested_at=NOW.replace(tzinfo=None))


def test_non_utc_offsets_normalize_to_same_utc_instant():
    local = datetime(2026, 10, 23, 16, 30, tzinfo=IST)
    obs = report(observed_at=local, ingested_at=NOW.astimezone(IST))
    assert obs.observed_at == NOW - timedelta(hours=1)
    assert obs.observed_at.tzinfo is UTC
    assert obs.ingested_at == NOW
    assert obs.ingested_at.tzinfo is UTC


def test_equivalent_offsets_produce_same_hotspot_time_and_freshness():
    utc_report = report(observed_at=NOW - timedelta(hours=1))
    offset_report = report(
        observed_at=(NOW - timedelta(hours=1)).astimezone(IST)
    )
    a = build_hotspots([utc_report], now=NOW)[0]
    b = build_hotspots([offset_report], now=NOW)[0]
    assert a.last_observed_at == b.last_observed_at
    assert a.freshness == b.freshness
    assert a.independent_sources == b.independent_sources == 1
