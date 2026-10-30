"""E413: strict historical snapshots must not use information received later.

All fixtures are synthetic. The live E411 five-minute clock-skew policy is
intentionally unchanged; this test exercises an opt-in historical helper.
"""
from datetime import UTC, datetime, timedelta

from utsav_sensor.fusion import build_hotspots, build_hotspots_as_of
from utsav_sensor.models import Observation

AS_OF = datetime(2026, 10, 30, 8, tzinfo=UTC)


def report(source: str, observed_min: int, ingested_min: int, status: str,
           provenance: str = "observed") -> Observation:
    return Observation(
        id=f"{source}-{observed_min}-{ingested_min}-{status}",
        source_type="partner" if provenance == "measured" else "citizen",
        source_id=source,
        provenance=provenance,
        observed_at=AS_OF + timedelta(minutes=observed_min),
        ingested_at=AS_OF + timedelta(minutes=ingested_min),
        lat=19.076, lon=72.8777, confidence=0.8,
        mass_kg_low=10, mass_kg_high=12, status=status,
    )


def test_backfilled_cleanup_cannot_rewrite_earlier_historical_snapshot():
    original = report("observer", -240, -180, "open")
    # The cleanup was physically observed before the snapshot, but was only
    # ingested two hours AFTER it. Historical knowledge cannot include it.
    late = report("partner", -120, 120, "cleaned", "measured")
    live_reconstruction = build_hotspots([original, late], AS_OF)
    assert live_reconstruction[0].status == "cleaned"  # known legacy boundary
    historical = build_hotspots_as_of([original, late], AS_OF)
    assert len(historical) == 1
    assert historical[0].status == "open"
    assert historical[0].unresolved_hours == 4
    assert historical[0].observation_count == 1


def test_event_time_also_must_not_exceed_historical_cutoff_even_by_one_second():
    original = report("observer", -240, -180, "open")
    premature = report("partner", 1, -10, "cleaned", "measured")
    historical = build_hotspots_as_of([original, premature], AS_OF)
    assert len(historical) == 1
    assert historical[0].status == "open"
    assert historical[0].observation_count == 1


def test_on_time_declared_cleanup_still_resolves_episode():
    original = report("observer", -240, -180, "open")
    cleanup = report("partner", -120, -60, "cleaned", "measured")
    historical = build_hotspots_as_of([original, cleanup], AS_OF)
    assert len(historical) == 1
    assert historical[0].status == "cleaned"
    assert historical[0].unresolved_hours == 0


def test_future_ingested_only_records_are_not_visible_and_input_is_unchanged():
    late = report("partner", -120, 120, "cleaned", "measured")
    observations = [late]
    assert build_hotspots_as_of(observations, AS_OF) == []
    assert observations == [late]


def test_exact_boundary_is_inclusive_and_existing_72_hour_window_is_preserved():
    boundary = report("observer", 0, 0, "open")
    too_old = report("older", -73 * 60, -73 * 60, "open")
    historical = build_hotspots_as_of([boundary, too_old], AS_OF)
    assert len(historical) == 1
    assert historical[0].observation_ids == [boundary.id]
