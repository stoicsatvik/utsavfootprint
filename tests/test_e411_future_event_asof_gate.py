"""E411: future-dated evidence must not resolve a hotspot in an as-of snapshot.

Synthetic timestamps and observations only. This does not authenticate
cleanup provenance, verify physical pile identity or establish field accuracy.
"""
from datetime import UTC, datetime, timedelta

import pytest

from utsav_sensor.fusion import build_hotspots, fuse_cluster
from utsav_sensor.models import Observation

NOW = datetime(2026, 10, 30, 8, tzinfo=UTC)


def report(source: str, age_minutes: float, status: str, provenance: str = "observed") -> Observation:
    return Observation(
        id=f"{source}-{status}-{age_minutes}",
        source_type="partner" if provenance == "measured" else "citizen",
        source_id=source,
        provenance=provenance,
        observed_at=NOW - timedelta(minutes=age_minutes),
        ingested_at=NOW,
        lat=19.076,
        lon=72.8777,
        confidence=0.8,
        mass_kg_low=10,
        mass_kg_high=12,
        status=status,
    )


def test_future_declared_cleanup_cannot_close_current_open_episode():
    open_report = report("observer", 240, "open")
    future_cleanup = report("partner", -120, "cleaned", "measured")
    states = build_hotspots([open_report, future_cleanup], NOW)
    assert len(states) == 1
    assert states[0].status == "open"
    assert states[0].unresolved_hours == 4
    assert states[0].observation_count == 1


def test_future_only_evidence_is_not_current_hotspot():
    assert build_hotspots([report("future", -120, "verified", "measured")], NOW) == []


def test_direct_fusion_rejects_future_evidence_outside_clock_skew():
    with pytest.raises(ValueError, match="future"):
        fuse_cluster([report("observer", 240, "open"),
                      report("partner", -120, "cleaned", "measured")], NOW)


def test_past_confirmed_cleanup_still_closes_episode():
    states = build_hotspots([
        report("observer", 240, "open"),
        report("partner", 120, "cleaned", "measured"),
    ], NOW)
    assert len(states) == 1
    assert states[0].status == "cleaned"
    assert states[0].unresolved_hours == 0


def test_small_clock_skew_does_not_discard_report():
    states = build_hotspots([report("observer", -1 / 60, "open")], NOW)
    assert len(states) == 1
    assert states[0].observation_count == 1
