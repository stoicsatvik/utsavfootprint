"""E170: correlated reports must not relocate a hotspot or change its clustering.

Synthetic software invariance tests, not evidence of field geolocation accuracy.
"""
import math
import random
from datetime import UTC, datetime, timedelta

from utsav_sensor.fusion import cluster_observations, fuse_cluster
from utsav_sensor.models import Observation

NOW = datetime(2026, 10, 23, 10, 0, tzinfo=UTC)


def report(source: str, lat: float, *, minute: int = 0, confidence: float = 1.0) -> Observation:
    return Observation(
        source_type="partner",
        provenance="measured",
        source_id=source,
        lat=lat,
        lon=72.8777,
        observed_at=NOW + timedelta(minutes=minute),
        confidence=confidence,
    )


def replays(obs: Observation, count: int) -> list[Observation]:
    # New report IDs are intentional: these are distinct ingested records
    # from the same correlated source, not database upserts of the same ID.
    return [obs.model_copy(update={"id": f"replay-{obs.source_id}-{i}"}) for i in range(count)]


def source_groups(clusters: list[list[Observation]]) -> list[tuple[str, ...]]:
    return sorted(tuple(sorted({o.source_id for o in cluster})) for cluster in clusters)


def test_fused_coordinates_ignore_identical_same_source_replays():
    a, b = report("A", 19.076), report("B", 19.077)
    baseline = fuse_cluster([a, b], now=NOW)
    replayed = fuse_cluster([a, b, *replays(b, 100)], now=NOW)
    assert math.isclose(baseline.lat, 19.0765, abs_tol=1e-12)
    assert math.isclose(replayed.lat, baseline.lat, abs_tol=1e-12)
    assert math.isclose(replayed.lon, baseline.lon, abs_tol=1e-12)
    assert replayed.independent_sources == 2
    assert replayed.observation_count == 102


def test_within_source_distinct_coordinate_claims_are_not_volume_weighted():
    a1, a2, b = report("A", 19.076), report("A", 19.0764), report("B", 19.077)
    baseline = fuse_cluster([a1, a2, b], now=NOW)
    replayed = fuse_cluster([a1, a2, b, *replays(a2, 50)], now=NOW)
    assert math.isclose(baseline.lat, 19.0766, abs_tol=1e-12)
    assert math.isclose(replayed.lat, baseline.lat, abs_tol=1e-12)


def test_cluster_membership_is_not_changed_by_same_source_replays():
    # A and B are within 120m. C is >120m from their balanced midpoint,
    # but <120m from B. Replaying B must not pull C into the first cluster.
    a = report("A", 19.076, minute=0)
    b = report("B", 19.077, minute=1)
    c = report("C", 19.078, minute=2)
    baseline = source_groups(cluster_observations([a, b, c]))
    replayed = source_groups(cluster_observations([a, b, *replays(b, 100), c]))
    assert baseline == [("A", "B"), ("C",)]
    assert replayed == baseline


def test_genuinely_independent_source_can_move_center():
    a, b, c = report("A", 19.076), report("B", 19.077), report("C", 19.078)
    before = fuse_cluster([a, b], now=NOW)
    after = fuse_cluster([a, b, c], now=NOW)
    assert math.isclose(before.lat, 19.0765, abs_tol=1e-12)
    assert math.isclose(after.lat, 19.077, abs_tol=1e-12)


def test_zero_strength_coordinates_remain_geographic_not_zero_zero():
    a = report("A", 19.076, confidence=0.0)
    b = report("B", 19.077, confidence=0.0)
    state = fuse_cluster([a, b, *replays(b, 100)], now=NOW)
    assert math.isclose(state.lat, 19.0765, abs_tol=1e-12)
    assert math.isclose(state.lon, 72.8777, abs_tol=1e-12)
    assert state.confidence == 0.0


def test_randomized_coordinate_replays_preserve_fused_location():
    rng = random.Random(170)
    for _ in range(250):
        reports = [
            report(
                f"source-{i}",
                19.076 + rng.randrange(-100, 101) / 100_000,
                confidence=rng.randrange(1, 101) / 100,
            )
            for i in range(rng.randint(2, 8))
        ]
        baseline = fuse_cluster(reports, now=NOW)
        repeated = reports[rng.randrange(len(reports))]
        replayed = [*reports, *replays(repeated, rng.randint(1, 50))]
        rng.shuffle(replayed)
        result = fuse_cluster(replayed, now=NOW)
        assert result.independent_sources == baseline.independent_sources
        assert result.lat == baseline.lat
        assert result.lon == baseline.lon
