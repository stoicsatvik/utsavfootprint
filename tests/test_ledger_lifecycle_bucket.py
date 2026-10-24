"""Synthetic regression for status transitions inside a 20-minute ledger bucket."""

from datetime import UTC, datetime, timedelta

from utsav_sensor.models import Observation
from utsav_sensor.place_query import summarize_coordinates

BASE = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
LAT, LON = 19.1947, 72.9737


def report(name: str, minute: int, status: str, low: float | None, high: float | None):
    return Observation(
        id=name,
        source_type="partner",
        provenance="measured",
        source_id=name,
        lat=LAT,
        lon=LON,
        observed_at=BASE + timedelta(minutes=minute),
        ingested_at=BASE + timedelta(minutes=minute),
        confidence=0.9,
        status=status,
        mass_kg_low=low,
        mass_kg_high=high,
    )


def summary(*records: Observation):
    return summarize_coordinates(
        list(records),
        LAT,
        LON,
        radius_m=100,
        start=BASE - timedelta(minutes=1),
        end=BASE + timedelta(minutes=19),
    )


def test_cleanup_inside_same_bucket_does_not_disappear():
    result = summary(
        report("mass", 0, "open", 100, 120),
        report("cleanup", 5, "cleaned", None, None),
    )
    assert result.generated_mass_kg_low == 100
    assert result.removed_mass_kg_low == 100
    assert result.current_mass_kg_low == 0
    assert result.unresolved_waste_hours_low == 0


def test_cleanup_then_reopen_inside_same_bucket_preserves_both_epochs():
    result = summary(
        report("old-mass", 0, "open", 100, 120),
        report("cleanup", 5, "cleaned", None, None),
        report("new-mass", 10, "open", 20, 25),
    )
    assert result.generated_mass_kg_low == 120
    assert result.generated_mass_kg_high == 145
    assert result.removed_mass_kg_low == 100
    assert result.removed_mass_kg_high == 120
    assert result.current_mass_kg_low == 20
    assert result.current_mass_kg_high == 25


def test_open_after_cleanup_inside_same_bucket_is_not_discarded():
    result = summary(
        report("cleanup", 0, "cleaned", None, None),
        report("reopened", 5, "open", 20, 25),
    )
    assert result.generated_mass_kg_low == 20
    assert result.current_mass_kg_low == 20
