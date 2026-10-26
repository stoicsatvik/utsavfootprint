"""E314: falsify naive longitude centroids and zero-strength coordinate collapse."""
from datetime import UTC, datetime

import pytest

from utsav_sensor.fusion import build_hotspots, cluster_observations
from utsav_sensor.models import Observation


def report(id: str, longitude: float, *, latitude: float = 0.0, confidence: float = 0.8):
    return Observation(
        id=id,
        source_type="citizen",
        provenance="observed",
        source_id=id,
        lat=latitude,
        lon=longitude,
        observed_at=datetime(2026, 10, 27, tzinfo=UTC),
        ingested_at=datetime(2026, 10, 27, tzinfo=UTC),
        confidence=confidence,
    )


def test_dateline_neighbor_reports_are_not_split_by_arithmetic_centroid():
    reports = [report("a", 179.9998), report("b", -179.9998), report("c", 179.9997)]
    groups = cluster_observations(reports, radius_m=120)
    assert len(groups) == 1
    assert {o.id for o in groups[0]} == {"a", "b", "c"}
    hotspot = build_hotspots(reports, now=datetime(2026, 10, 27, tzinfo=UTC))[0]
    assert hotspot.observation_count == 3
    assert abs(abs(hotspot.lon) - 180.0) < 0.001
    assert hotspot.lat == pytest.approx(0.0)


def test_zero_strength_report_retains_its_geographic_location():
    reports = [report("zero", 72.8777, latitude=19.076, confidence=0.0)]
    hotspot = build_hotspots(reports, now=datetime(2026, 10, 27, tzinfo=UTC))[0]
    assert hotspot.confidence == 0.0
    assert hotspot.lat == pytest.approx(19.076)
    assert hotspot.lon == pytest.approx(72.8777)


def test_zero_strength_dateline_reports_still_have_correct_centroid():
    reports = [report("a", 179.9998, confidence=0.0), report("b", -179.9998, confidence=0.0)]
    hotspot = build_hotspots(reports, now=datetime(2026, 10, 27, tzinfo=UTC))[0]
    assert hotspot.confidence == 0.0
    assert abs(abs(hotspot.lon) - 180.0) < 0.001


def test_non_dateline_center_preserved():
    reports = [report("a", 72.8777), report("b", 72.8779)]
    hotspot = build_hotspots(reports, now=datetime(2026, 10, 27, tzinfo=UTC))[0]
    assert hotspot.lon == pytest.approx(72.8778, abs=1e-8)
