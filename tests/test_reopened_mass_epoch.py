"""E460: a credible cleanup separates historical and reopened mass episodes.

All inputs are synthetic and provenance labels are declarations, not authenticated
proof of physical cleanup. No real waste mass is inferred.
"""
from datetime import UTC, datetime, timedelta

from utsav_sensor.fusion import fuse_cluster
from utsav_sensor.models import Observation

NOW = datetime(2026, 11, 1, 0, 0, tzinfo=UTC)
OLD = NOW - timedelta(hours=3)
CLOSED = NOW - timedelta(hours=2)
NEW = NOW - timedelta(hours=1)


def report(name, when, provenance="observed", status="open", low=None, high=None):
    return Observation(
        id=name, source_id=name, source_type="partner" if provenance == "measured" else "citizen",
        provenance=provenance, lat=19.076, lon=72.8777, observed_at=when,
        ingested_at=when, confidence=0.8, mass_kg_low=low, mass_kg_high=high,
        status=status,
    )


def historical():
    return report("old-scale", OLD, "measured", low=100, high=120)


def cleanup():
    return report("official-clean", CLOSED, "verified_official", "cleaned")


def test_reopened_mass_does_not_reuse_precleanup_high_rank_measurement():
    h = fuse_cluster([historical(), cleanup(), report("new", NEW, low=2, high=4)], NOW)
    assert h.status == "open"
    assert (h.mass_kg_low, h.mass_kg_high, h.mass_basis) == (2, 4, "observed")


def test_reopened_without_mass_abstains_instead_of_resurrecting_old_mass():
    h = fuse_cluster([historical(), cleanup(), report("new", NEW)], NOW)
    assert h.status == "open"
    assert (h.mass_kg_low, h.mass_kg_high, h.mass_basis) == (None, None, None)
    assert h.unresolved_waste_hours_low is None


def test_no_credible_cleanup_keeps_original_provenance_priority():
    h = fuse_cluster([historical(), report("new", NEW, low=2, high=4)], NOW)
    assert (h.mass_kg_low, h.mass_kg_high, h.mass_basis) == (100, 120, "measured")


def test_closed_hotspot_retains_historical_mass_as_historical_evidence():
    h = fuse_cluster([historical(), cleanup()], NOW)
    assert h.status == "cleaned"
    assert (h.mass_kg_low, h.mass_kg_high) == (100, 120)
    assert h.unresolved_waste_hours_low == 0


def test_unverified_cleanup_cannot_reset_mass_epoch():
    unverified = report("citizen-clean", CLOSED, "observed", "cleaned")
    h = fuse_cluster([historical(), unverified, report("new", NEW, low=2, high=4)], NOW)
    assert (h.mass_kg_low, h.mass_kg_high) == (100, 120)


def test_equal_time_open_and_cleanup_abstains_from_ambiguous_mass():
    closure_mass = report("closure-scale", CLOSED, "measured", "cleaned", 100, 120)
    h = fuse_cluster([historical(), closure_mass, report("new", CLOSED, low=2, high=4)], NOW)
    assert h.status == "open"
    assert (h.mass_kg_low, h.mass_kg_high) == (None, None)


def test_latest_of_multiple_cleanups_defines_reopened_mass_epoch():
    second = report("second-clean", NOW - timedelta(minutes=45), "measured", "verified")
    late = report("latest", NOW - timedelta(minutes=15), low=3, high=5)
    h = fuse_cluster([historical(), cleanup(), report("interim", NEW, low=9, high=11), second, late], NOW)
    assert (h.mass_kg_low, h.mass_kg_high) == (3, 5)
