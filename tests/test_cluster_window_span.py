"""E173: temporal windows bound the full span of a hotspot cluster.

These synthetic contract tests distinguish a 24-hour *cluster span* from a
24-hour maximum gap between consecutive reports. No field data is used.
"""

import random
from datetime import UTC, datetime, timedelta

from utsav_sensor.fusion import cluster_observations
from utsav_sensor.models import Observation

BASE = datetime(2026, 10, 23, 0, 0, tzinfo=UTC)


def report(source: str, offset: timedelta) -> Observation:
    return Observation(
        id=f"{source}-report",
        source_type="partner",
        provenance="measured",
        source_id=source,
        lat=19.076,
        lon=72.8777,
        observed_at=BASE + offset,
    )


def source_groups(reports: list[Observation]) -> list[tuple[str, ...]]:
    return sorted(
        tuple(sorted(obs.source_id for obs in cluster))
        for cluster in cluster_observations(reports, window_hours=24)
    )


def test_transitive_23_hour_gaps_must_not_create_46_hour_cluster():
    # The original newest-only comparison accepts A->B and B->C,
    # accidentally placing observations 46 hours apart in one cluster.
    reports = [
        report("A", timedelta(hours=0)),
        report("B", timedelta(hours=23)),
        report("C", timedelta(hours=46)),
    ]
    assert source_groups(reports) == [("A", "B"), ("C",)]
    assert source_groups(list(reversed(reports))) == [("A", "B"), ("C",)]


def test_window_includes_exact_boundary_but_excludes_one_second_beyond():
    on_boundary = [
        report("A", timedelta()),
        report("B", timedelta(hours=24)),
    ]
    outside = [
        report("A", timedelta()),
        report("B", timedelta(hours=24, seconds=1)),
    ]
    assert source_groups(on_boundary) == [("A", "B")]
    assert source_groups(outside) == [("A",), ("B",)]


def test_seeded_clusters_never_exceed_configured_full_span():
    rng = random.Random(173)
    for trial in range(200):
        elapsed_minutes = 0
        reports = []
        for i in range(rng.randint(3, 20)):
            elapsed_minutes += rng.randint(0, 23 * 60)
            reports.append(report(f"s{trial}-{i}", timedelta(minutes=elapsed_minutes)))
        rng.shuffle(reports)
        clusters = cluster_observations(reports, window_hours=24)
        assert sum(len(cluster) for cluster in clusters) == len(reports)
        for cluster in clusters:
            times = [item.observed_at for item in cluster]
            assert (max(times) - min(times)).total_seconds() <= 24 * 3600
