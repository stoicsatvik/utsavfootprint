"""E336: adversarial spatial/time linkage and independent complete-link oracle.

All observations are synthetic. Pairwise caps are a conservative contract,
not proof of one physical pile or a measured waste-detection accuracy.
"""

import math
import random
from datetime import UTC, datetime, timedelta

import pytest

from utsav_sensor.fusion import (
    _spherical_centroid,
    build_hotspots,
    cluster_observations,
    haversine_m,
)
from utsav_sensor.models import Observation

NOW = datetime(2026, 10, 27, tzinfo=UTC)
EARTH_RADIUS_M = 6_371_000.0


def point(name: str, east_m: float, *, base_lon: float = 72.8777, hour: int = 0):
    lon = ((base_lon + math.degrees(east_m / EARTH_RADIUS_M) + 180) % 360) - 180
    return Observation(
        id=name,
        source_type="citizen",
        provenance="observed",
        source_id=name,
        lat=0.0,
        lon=lon,
        observed_at=NOW + timedelta(hours=hour),
        ingested_at=NOW,
        confidence=0.8,
        mass_kg_low=1.0,
        mass_kg_high=2.0,
    )


def diameter(cluster):
    return max(
        (haversine_m(a.lat, a.lon, b.lat, b.lon) for a in cluster for b in cluster),
        default=0.0,
    )


def span_hours(cluster):
    return (max(o.observed_at for o in cluster) - min(o.observed_at for o in cluster)).total_seconds() / 3600


def legacy_centroid_greedy(observations, radius_m=120.0, window_hours=24.0):
    """Frozen pre-E336 rule, reproduced solely as a negative control."""
    groups = []
    for obs in sorted(observations, key=lambda o: (o.observed_at, o.id)):
        best = None
        best_d = float("inf")
        for group in groups:
            newest = max(o.observed_at for o in group)
            if abs((obs.observed_at - newest).total_seconds()) > window_hours * 3600:
                continue
            lat, lon = _spherical_centroid(group)
            d = haversine_m(obs.lat, obs.lon, lat, lon)
            if d <= radius_m and d < best_d:
                best, best_d = group, d
        if best is None:
            groups.append([obs])
        else:
            best.append(obs)
    return groups


def complete_link_oracle(observations, radius_m=120.0, window_hours=24.0):
    """Independent agglomerative reference with pairwise max-distance linkage.

    This is a comparator, not ground truth. It uses a deterministic tie-break
    and never merges clusters exceeding the spatial or temporal cap.
    """
    groups = [[o] for o in sorted(observations, key=lambda o: o.id)]
    while True:
        candidates = []
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                union = groups[i] + groups[j]
                d = diameter(union)
                if d <= radius_m and span_hours(union) <= window_hours:
                    ids = tuple(sorted(o.id for o in union))
                    candidates.append((d, ids, i, j))
        if not candidates:
            break
        _, _, i, j = min(candidates)
        groups[i].extend(groups.pop(j))
    return groups


def connected_components_oracle(observations, radius_m=120.0, window_hours=24.0):
    """Independent DBSCAN-minPts=1-like transitive-neighbour comparator."""
    remaining = {o.id: o for o in observations}
    groups = []
    while remaining:
        first = min(remaining)
        group = [remaining.pop(first)]
        for obs in group:
            for key in sorted(list(remaining)):
                candidate = remaining[key]
                dt = abs((obs.observed_at - candidate.observed_at).total_seconds())
                if dt <= window_hours * 3600 and haversine_m(
                    obs.lat, obs.lon, candidate.lat, candidate.lon
                ) <= radius_m:
                    group.append(remaining.pop(key))
        groups.append(group)
    return groups


@pytest.mark.parametrize("base_lon", [72.8777, 179.999])
def test_spatial_chain_falsifies_centroid_radius_and_is_conservatively_split(base_lon):
    points = [point(chr(97 + i), m, base_lon=base_lon) for i, m in enumerate([0, 100, 165, 205])]
    before = legacy_centroid_greedy(points)
    after = cluster_observations(points)
    oracle = complete_link_oracle(points)
    connected = connected_components_oracle(points)

    assert len(before) == 1
    assert diameter(before[0]) == pytest.approx(205.0, abs=0.001)
    assert len(connected) == 1  # transitive neighbour closure also overmerges
    assert sorted(len(group) for group in after) == [2, 2]
    assert sorted(len(group) for group in oracle) == [2, 2]
    assert all(diameter(group) <= 120.0 for group in after)
    assert sorted(h.observation_count for h in build_hotspots(points, now=NOW)) == [2, 2]


def test_time_chain_falsifies_newest_only_window():
    points = [point("a", 0, hour=0), point("b", 0, hour=23), point("c", 0, hour=46)]
    before = legacy_centroid_greedy(points)
    after = cluster_observations(points)
    assert len(before) == 1 and span_hours(before[0]) == 46
    assert sorted(len(group) for group in after) == [1, 2]
    assert all(span_hours(group) <= 24 for group in after)
    assert sorted(len(group) for group in complete_link_oracle(points)) == [1, 2]


def test_compact_and_separated_controls_do_not_regress():
    compact = [point(chr(97 + i), m) for i, m in enumerate([0, 40, 80])]
    separated = [point(chr(97 + i), m) for i, m in enumerate([0, 300, 600])]
    assert len(cluster_observations(compact)) == 1
    assert len(cluster_observations(separated)) == 3


def test_polar_and_dateline_close_pairs_remain_grouped():
    polar = [
        point("a", 0).model_copy(update={"lat": 89.9995, "lon": 0}),
        point("b", 0).model_copy(update={"lat": 89.9995, "lon": 180}),
    ]
    assert 110 < diameter(polar) < 112
    assert len(cluster_observations(polar)) == 1
    dateline = [point("a", 0, base_lon=179.9999), point("b", 30, base_lon=179.9999)]
    assert len(cluster_observations(dateline)) == 1


def test_renaming_can_still_change_greedy_partition_negative_result():
    original = [point("a", 0), point("b", 100), point("c", 200)]
    renamed = [
        o.model_copy(update={"id": name, "source_id": name})
        for o, name in zip(original, ["c", "b", "a"], strict=True)
    ]
    def positions(groups):
        return sorted(
            tuple(sorted(round((o.lon - 72.8777) * math.pi / 180 * EARTH_RADIUS_M)
                         for o in group))
            for group in groups
        )
    assert positions(cluster_observations(original)) != positions(cluster_observations(renamed))
    assert all(diameter(group) <= 120 for group in cluster_observations(renamed))


def test_seeded_spatiotemporal_invariants_without_ground_truth():
    for seed in range(64):
        rng = random.Random(seed)
        reports = [
            point(
                f"seed{seed}_id{i}",
                rng.uniform(-350, 350),
                hour=rng.randint(0, 48),
            )
            for i in range(rng.randint(4, 12))
        ]
        groups = cluster_observations(reports)
        assert sum(map(len, groups)) == len(reports)
        assert len({o.id for group in groups for o in group}) == len(reports)
        assert all(diameter(group) <= 120 + 1e-7 for group in groups)
        assert all(span_hours(group) <= 24 for group in groups)
        assert {
            tuple(sorted(o.id for o in group)) for group in groups
        } == {
            tuple(sorted(o.id for o in group))
            for group in cluster_observations(list(reversed(reports)))
        }
