"""E410: conservative lifecycle semantics for synthetic hotspot observations.

All reports and provenance are fabricated fixtures. These tests do not
authenticate sources or establish real cleanup, pile identity, or field accuracy.
"""
from datetime import UTC, datetime, timedelta

from utsav_sensor.fusion import fuse_cluster
from utsav_sensor.models import Observation

NOW = datetime(2026, 10, 30, 8, tzinfo=UTC)


def report(source: str, hours_ago: float, status: str, provenance: str = "observed") -> Observation:
    return Observation(
        id=f"{source}-{status}-{hours_ago}",
        source_type="partner" if provenance == "measured" else "citizen",
        source_id=source,
        provenance=provenance,
        observed_at=NOW - timedelta(hours=hours_ago),
        ingested_at=NOW,
        lat=19.076,
        lon=72.8777,
        confidence=0.8,
        mass_kg_low=10,
        mass_kg_high=12,
        status=status,
    )


def test_confirmed_cleanup_closes_earlier_open_episode():
    state = fuse_cluster([
        report("citizen", 4, "open"),
        report("scale-partner", 2, "cleaned", "measured"),
    ], NOW)
    assert state.status == "cleaned"
    assert state.unresolved_hours == 0
    assert state.unresolved_waste_hours_low == 0


def test_later_open_restarts_duration_after_confirmed_cleanup():
    state = fuse_cluster([
        report("citizen", 4, "open"),
        report("scale-partner", 2, "cleaned", "measured"),
        report("new-observer", 1, "open"),
    ], NOW)
    assert state.status == "open"
    assert state.unresolved_hours == 1
    assert state.unresolved_waste_hours_low == 10


def test_unverified_cleanup_claim_does_not_close_earlier_open():
    state = fuse_cluster([
        report("citizen", 4, "open"),
        report("anonymous", 2, "cleaned", "observed"),
    ], NOW)
    assert state.status == "open"
    assert state.unresolved_hours == 4


def test_equal_timestamp_open_prevents_ambiguous_closure():
    state = fuse_cluster([
        report("citizen", 2, "open"),
        report("scale-partner", 2, "verified", "measured"),
    ], NOW)
    assert state.status == "open"
    assert state.unresolved_hours == 2
    reversed_state = fuse_cluster([
        report("scale-partner", 2, "verified", "measured"),
        report("citizen", 2, "open"),
    ], NOW)
    assert reversed_state.status == state.status
    assert reversed_state.unresolved_hours == state.unresolved_hours


def test_unverified_closed_only_cannot_claim_confirmed_resolution():
    state = fuse_cluster([report("anonymous", 3, "cleaned", "observed")], NOW)
    assert state.status == "open"
    assert state.unresolved_hours == 3


def test_later_confirmed_verification_closes_reopened_episode():
    state = fuse_cluster([
        report("a", 5, "open"),
        report("b", 4, "cleaned", "measured"),
        report("c", 2, "claimed"),
        report("d", 1, "verified", "verified_official"),
    ], NOW)
    assert state.status == "verified"
    assert state.unresolved_hours == 0
