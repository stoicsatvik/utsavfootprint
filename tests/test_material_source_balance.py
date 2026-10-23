"""E169: material estimates should weight independent sources, not report volume.

These are synthetic software invariance checks, not field calibration.
"""
import random
from datetime import UTC, datetime

from utsav_sensor.fusion import fuse_cluster
from utsav_sensor.models import Observation

NOW = datetime(2026, 10, 23, 9, 0, tzinfo=UTC)


def report(source: str, plastic: float | None, confidence: float = 1.0) -> Observation:
    return Observation(
        source_type="partner",
        provenance="measured",
        source_id=source,
        lat=19.076,
        lon=72.8777,
        observed_at=NOW,
        confidence=confidence,
        materials={} if plastic is None else {"plastic": plastic},
    )


def test_same_source_replays_cannot_outvote_an_independent_source():
    a, b = report("A", 0.2), report("B", 0.8)
    baseline = fuse_cluster([a, b], now=NOW)
    assert baseline.materials["plastic"] == 0.5
    for count in (1, 2, 10, 100):
        replay = fuse_cluster([a, *([b] * count)], now=NOW)
        assert replay.independent_sources == 2
        assert replay.materials["plastic"] == baseline.materials["plastic"]


def test_distinct_source_observations_are_robust_to_replaying_one_value():
    a_low, a_high, b = report("A", 0.1), report("A", 0.9), report("B", 0.5)
    baseline = fuse_cluster([a_low, a_high, b], now=NOW)
    replay = fuse_cluster([a_low, *([a_high] * 100), b], now=NOW)
    assert baseline.materials["plastic"] == 0.5
    assert replay.materials["plastic"] == baseline.materials["plastic"]


def test_new_source_changes_estimate_and_missing_key_is_not_zero():
    a, b, c = report("A", 0.2), report("B", 0.8), report("C", 0.8)
    assert fuse_cluster([a, b], now=NOW).materials["plastic"] == 0.5
    assert fuse_cluster([a, b, c], now=NOW).materials["plastic"] == 0.6
    assert fuse_cluster([a, report("missing", None), b], now=NOW).materials["plastic"] == 0.5


def test_strength_weighting_is_per_source_not_per_report():
    a, b = report("A", 0.0, 1.0), report("B", 1.0, 0.5)
    expected = round(0.5 / 1.5, 4)
    assert fuse_cluster([a, b], now=NOW).materials["plastic"] == expected
    assert fuse_cluster([a, *([b] * 100)], now=NOW).materials["plastic"] == expected


def test_randomized_same_source_replay_invariance():
    rng = random.Random(169)
    for _ in range(250):
        count = rng.randint(2, 8)
        reports = [report(f"source-{i}", rng.randint(0, 100) / 100) for i in range(count)]
        baseline = fuse_cluster(reports, now=NOW).materials
        duplicate = reports[rng.randrange(count)]
        replayed = reports + [duplicate] * rng.randint(1, 50)
        rng.shuffle(replayed)
        assert fuse_cluster(replayed, now=NOW).materials == baseline
