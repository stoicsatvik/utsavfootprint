"""E324: high-latitude centroid counterexamples and deterministic controls."""
from datetime import UTC, datetime

import pytest

from utsav_sensor.fusion import (
    _spherical_centroid, build_hotspots, cluster_observations,
    fuse_cluster, haversine_m,
)
from utsav_sensor.models import Observation

NOW = datetime(2026, 10, 27, tzinfo=UTC)


def report(name, latitude, longitude, confidence=0.8):
    return Observation(
        id=name, source_type="citizen", provenance="observed",
        source_id=name, lat=latitude, lon=longitude,
        observed_at=NOW, ingested_at=NOW, confidence=confidence,
    )


def test_polar_pair_has_pole_centroid_not_arithmetic_latitude():
    a, b = report("a", 89.9995, 0), report("b", 89.9995, 180)
    assert 110 < haversine_m(a.lat, a.lon, b.lat, b.lon) < 112
    assert len(cluster_observations([a, b], radius_m=120)) == 1
    hotspot = build_hotspots([a, b], now=NOW)[0]
    assert hotspot.lat == pytest.approx(90, abs=1e-8)
    # The old arithmetic-latitude midpoint is over 55 m from the pole.
    assert haversine_m(89.9995, 0, 90, 0) > 55


def test_three_high_latitude_observations_shift_centroid_poleward():
    points = [report("a", 89.9995, 0), report("b", 89.9995, 90),
              report("c", 89.9995, 180)]
    hotspot = fuse_cluster(points, NOW)
    assert 89.9997 < hotspot.lat < 90
    assert hotspot.lon == pytest.approx(90, abs=1e-6)


def test_antipodal_undefined_result_uses_stable_source_not_order():
    points = [report("z", 0, 0), report("a", 0, 180)]
    x = _spherical_centroid(points)
    y = _spherical_centroid(list(reversed(points)))
    assert x == y == (0, 180)


def test_zero_confidence_near_pole_preserves_position_not_zero_zero():
    points = [report("a", 89.9995, 0, 0), report("b", 89.9995, 180, 0)]
    hotspot = fuse_cluster(points, NOW)
    assert hotspot.confidence == 0
    assert hotspot.lat == pytest.approx(90, abs=1e-8)


def test_dateline_and_ordinary_midpoints_still_work():
    dateline = [report("a", 0, 179.9998), report("b", 0, -179.9998)]
    assert abs(abs(fuse_cluster(dateline, NOW).lon) - 180) < 0.001
    normal = [report("a", 0, 72.8777), report("b", 0, 72.8779)]
    assert fuse_cluster(normal, NOW).lon == pytest.approx(72.8778, abs=1e-8)


def test_invalid_weights_fail_closed():
    points = [report("a", 0, 0), report("b", 0, 1)]
    for weights in ([1], [float("nan"), 1], [-1, 2]):
        with pytest.raises(ValueError):
            _spherical_centroid(points, weights)
