"""E171: observation IDs are audit identifiers, not geospatial evidence.

These are synthetic clustering-contract tests, not field-location validation.
"""

from datetime import UTC, datetime, timedelta

from utsav_sensor.fusion import cluster_observations
from utsav_sensor.models import Observation

BASE = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


def report(source: str, lat: float, oid: str, *, minute: int = 0) -> Observation:
    return Observation(
        id=oid,
        source_type="partner",
        provenance="measured",
        source_id=source,
        lat=lat,
        lon=72.8777,
        observed_at=BASE + timedelta(minutes=minute),
    )


def groups(observations: list[Observation]) -> list[tuple[str, ...]]:
    return sorted(
        tuple(sorted({o.source_id for o in cluster}))
        for cluster in cluster_observations(observations)
    )


def test_equal_timestamp_id_renaming_does_not_change_cluster_membership():
    # A-B and B-C are ~111 m apart; A-C is ~222 m.
    # Greedy 120 m centroid clustering has two possible partitions.
    # UUID lexical order must not decide which physical observations join.
    forward = [
        report("A", 19.076, "01-a"),
        report("B", 19.077, "02-b"),
        report("C", 19.078, "03-c"),
    ]
    reverse_ids = [
        report("A", 19.076, "03-a"),
        report("B", 19.077, "02-b"),
        report("C", 19.078, "01-c"),
    ]
    expected = [("A", "B"), ("C",)]
    assert groups(forward) == expected
    assert groups(reverse_ids) == expected


def test_input_permutation_cannot_change_equal_timestamp_clusters():
    reports = [
        report("A", 19.076, "z"),
        report("B", 19.077, "a"),
        report("C", 19.078, "m"),
    ]
    expected = groups(reports)
    assert groups(list(reversed(reports))) == expected


def test_distinct_timestamps_still_take_precedence_over_coordinate_sorting():
    # Earlier C joins B before the later A is considered.
    observations = [
        report("A", 19.076, "a", minute=2),
        report("B", 19.077, "b", minute=1),
        report("C", 19.078, "c", minute=0),
    ]
    assert groups(observations) == [("A",), ("B", "C")]
