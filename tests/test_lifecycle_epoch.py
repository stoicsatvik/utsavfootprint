"""Regression evidence for cleanup/reopening epochs (synthetic, no field claims)."""

from datetime import UTC, datetime, timedelta
from math import isclose

from utsav_sensor.fusion import build_hotspots
from utsav_sensor.models import Observation

NOW = datetime(2026, 10, 24, 0, 0, tzinfo=UTC)


def event(event_id: str, hours_ago: float, status: str, low: float | None = 10,
          high: float | None = 20, *, ingested_minutes_later: float = 0) -> Observation:
    observed = NOW - timedelta(hours=hours_ago)
    return Observation(
        id=event_id,
        source_type="partner",
        provenance="measured",
        source_id=event_id,
        lat=19.076,
        lon=72.8777,
        observed_at=observed,
        ingested_at=observed + timedelta(minutes=ingested_minutes_later),
        confidence=0.95,
        status=status,
        mass_kg_low=low,
        mass_kg_high=high,
    )


def test_cleanup_closes_unresolved_hours_even_with_older_open_report():
    hotspot = build_hotspots(
        [event("open-old", 5, "open"), event("cleanup", 1, "cleaned")], now=NOW
    )[0]
    assert hotspot.status == "cleaned"
    assert hotspot.unresolved_hours == 0
    assert hotspot.unresolved_waste_hours_low == 0
    assert hotspot.unresolved_waste_hours_high == 0



def test_resolved_hotspot_with_no_mass_still_has_zero_unresolved_exposure():
    hotspot = build_hotspots(
        [
            event("old-report", 5, "open", 10, 20),
            event("verified-cleanup", 1, "verified", None, None),
        ],
        now=NOW,
    )[0]
    assert hotspot.mass_kg_low is None
    assert hotspot.mass_kg_high is None
    assert hotspot.unresolved_hours == 0
    assert hotspot.unresolved_waste_hours_low == 0
    assert hotspot.unresolved_waste_hours_high == 0


def test_reopening_starts_new_unresolved_epoch_without_old_mass_or_confidence():
    hotspot = build_hotspots(
        [
            event("old-measurement", 5, "open", 100, 120),
            event("cleanup", 2, "cleaned", 0, 0),
            event("new-observation", 0.5, "open", 5, 7),
        ],
        now=NOW,
    )[0]
    assert hotspot.status == "open"
    assert isclose(hotspot.unresolved_hours, 0.5, abs_tol=1e-9)
    assert hotspot.mass_kg_low == 5
    assert hotspot.mass_kg_high == 7
    assert isclose(hotspot.unresolved_waste_hours_low, 2.5, abs_tol=1e-9)
    assert hotspot.independent_sources == 1
    assert hotspot.observation_count == 3  # history remains auditable


def test_equal_observation_times_resolve_by_ingestion_order_not_input_order():
    open_event = event("a-open", 1, "open", ingested_minutes_later=0)
    closed_event = event("z-closed", 1, "verified", ingested_minutes_later=10)
    for ordered in ([open_event, closed_event], [closed_event, open_event]):
        hotspot = build_hotspots(ordered, now=NOW)[0]
        assert hotspot.status == "verified"
        assert hotspot.unresolved_hours == 0
