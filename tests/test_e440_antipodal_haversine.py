"""E440: antipodal floating-point domain regression for valid coordinates.

No real field data, waste detection, or geospatial accuracy claim.
"""
import math
import random
from datetime import UTC, datetime

import pytest

from utsav_sensor.fusion import cluster_observations, haversine_m
from utsav_sensor.models import Observation

R = 6_371_000.0
# Frozen valid near-antipodal coordinates. Unclamped q = 1.0000000000000004
# under CPython binary64; sqrt(q) > 1 and asin raises ValueError.
PAIR = (61.13111980259248, -103.81561493387612,
        -61.13111979418826, 76.1843851189758)


def test_unclamped_expression_reproduces_domain_error():
    a, b, c, d = PAIR
    p1, p2 = math.radians(a), math.radians(c)
    q = (math.sin(math.radians(c-a)/2)**2
         + math.cos(p1)*math.cos(p2)*math.sin(math.radians(d-b)/2)**2)
    assert q > 1.0
    with pytest.raises(ValueError):
        math.asin(math.sqrt(q))
    assert haversine_m(*PAIR) == pytest.approx(math.pi * R, abs=0.01)


def test_valid_near_antipodal_reports_do_not_crash_clustering():
    now = datetime(2026, 10, 31, tzinfo=UTC)
    reports = [
        Observation(id=str(i), source_type="citizen", provenance="observed",
                    source_id=str(i), lat=lat, lon=lon,
                    observed_at=now, ingested_at=now)
        for i, (lat, lon) in enumerate(((PAIR[0], PAIR[1]), (PAIR[2], PAIR[3])))
    ]
    clusters = cluster_observations(reports)
    assert len(clusters) == 2
    assert sorted(len(cluster) for cluster in clusters) == [1, 1]


def test_same_point_and_dateline():
    assert haversine_m(10, 20, 10, 20) == 0
    assert haversine_m(0, 179.999, 0, -179.999) == pytest.approx(222.389853, abs=0.001)


def test_equatorial_degree():
    assert haversine_m(0, 0, 0, 1) == pytest.approx(math.pi * R / 180, rel=1e-13)


def test_frozen_random_valid_coordinates_stay_bounded_and_symmetric():
    rng = random.Random(440)
    for _ in range(10_000):
        a = (rng.uniform(-90, 90), rng.uniform(-180, 180))
        b = (rng.uniform(-90, 90), rng.uniform(-180, 180))
        d = haversine_m(*a, *b)
        assert math.isfinite(d) and 0 <= d <= math.pi * R + 1e-7
        assert d == pytest.approx(haversine_m(*b, *a), rel=2e-13, abs=1e-7)
