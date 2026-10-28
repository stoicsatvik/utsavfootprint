"""E336: adversarial spatial/time linkage and independent complete-link oracle.

All observations are synthetic. Pairwise caps are a conservative contract,
not proof of one physical pile or a measured waste-detection accuracy.
"""

import itertools
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
            for key in sorted(remaining):
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


@pytest.mark.parametrize("base_lon", [72.8777, 179.999])
def test_distinct_positions_have_id_invariant_partition(base_lon):
    """Six ID assignments cannot change the same three physical observations."""
    original = [point(str(i), m, base_lon=base_lon) for i, m in enumerate([0, 100, 200])]

    def spatial_partition(groups):
        return sorted(
            tuple(sorted(round(haversine_m(o.lat, o.lon, original[0].lat, original[0].lon))
                         for o in group))
            for group in groups
        )

    reference = spatial_partition(cluster_observations(original))
    assert reference == [(0, 100), (200,)]
    for names in itertools.permutations(("a", "b", "c")):
        renamed = [
            o.model_copy(update={"id": name, "source_id": name})
            for o, name in zip(original, names, strict=True)
        ]
        assert spatial_partition(cluster_observations(renamed)) == reference
        assert spatial_partition(cluster_observations(list(reversed(renamed)))) == reference
        assert all(diameter(group) <= 120 for group in cluster_observations(renamed))


def test_canonical_sort_is_not_a_ground_truth_identity_model():
    """The 0/100/200 chain remains ambiguous without physical pile labels."""
    reports = [point(str(i), m) for i, m in enumerate((0, 100, 200))]
    groups = cluster_observations(reports)
    assert sorted(len(group) for group in groups) == [1, 2]
    assert all(diameter(group) <= 120 for group in groups)
    # An equally valid bounded partition pairs 100 and 200 instead.
    alternative = [[reports[0]], [reports[1], reports[2]]]
    assert all(diameter(group) <= 120 for group in alternative)
    assert spatial_signature(groups) != spatial_signature(alternative)


def spatial_signature(groups):
    return sorted(tuple(sorted(round(o.lon, 8) for o in group)) for group in groups)


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


@pytest.mark.parametrize("base_lon", [72.8777, 179.999])
def test_microsecond_timestamp_jitter_changes_ambiguous_greedy_partition(base_lon):
    """A 2-microsecond total timing spread can change physical grouping.

    This is a preserved negative robustness result, not a failing test.
    Both partitions obey the spatial and temporal caps.
    """
    original = [
        point(name, east_m, base_lon=base_lon)
        for name, east_m in zip(("a", "b", "c"), (0, 100, 200), strict=True)
    ]
    jittered = [
        original[0].model_copy(
            update={"observed_at": NOW + timedelta(microseconds=1)}
        ),
        original[1],
        original[2].model_copy(
            update={"observed_at": NOW - timedelta(microseconds=1)}
        ),
    ]

    def memberships(reports):
        return {
            tuple(sorted(o.id for o in group))
            for group in cluster_observations(reports)
        }

    assert memberships(original) == {("a", "b"), ("c",)}
    assert memberships(jittered) == {("a",), ("b", "c")}
    assert memberships(jittered) == memberships(list(reversed(jittered)))
    assert [o.lat for o in original] == [o.lat for o in jittered]
    assert [o.lon for o in original] == [o.lon for o in jittered]
    for reports in (original, jittered):
        groups = cluster_observations(reports)
        assert sum(len(group) for group in groups) == 3
        assert all(diameter(group) <= 120.0 for group in groups)
        assert all(span_hours(group) <= 24.0 for group in groups)
