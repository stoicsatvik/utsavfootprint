"""E168: mass fusion must not count report volume as independent evidence."""
from datetime import UTC, datetime
import random
from statistics import median

from utsav_sensor.fusion import fuse_cluster
from utsav_sensor.models import Observation


NOW = datetime(2026, 10, 23, 9, 0, tzinfo=UTC)


def report(source: str, low: float, high: float) -> Observation:
    return Observation(
        source_type="partner",
        provenance="measured",
        source_id=source,
        lat=19.076,
        lon=72.8777,
        confidence=1.0,
        observed_at=NOW,
        mass_kg_low=low,
        mass_kg_high=high,
    )


def test_duplicate_reports_do_not_shift_independent_source_median():
    first = report("A", 100, 100)
    second = report("B", 200, 200)
    for repetitions in (1, 2, 10, 100):
        state = fuse_cluster([first] + [second] * repetitions, now=NOW)
        assert state.independent_sources == 2
        assert (state.mass_kg_low, state.mass_kg_high) == (150, 150)


def test_new_independent_source_can_change_estimate():
    state = fuse_cluster(
        [report("A", 100, 100), report("B", 200, 200), report("C", 300, 300)],
        now=NOW,
    )
    assert state.independent_sources == 3
    assert (state.mass_kg_low, state.mass_kg_high) == (200, 200)


def test_synthetic_randomized_replay_invariance():
    rng = random.Random(168)
    for _ in range(200):
        count = rng.randint(2, 7)
        reports = []
        for index in range(count):
            low = rng.randint(0, 1000)
            reports.append(report(f"source-{index}", low, low + rng.randint(0, 1000)))
        baseline = fuse_cluster(reports, now=NOW)
        duplicate = reports[rng.randrange(len(reports))]
        with_replays = reports + [duplicate] * rng.randint(1, 20)
        rng.shuffle(with_replays)
        state = fuse_cluster(with_replays, now=NOW)
        assert state.independent_sources == baseline.independent_sources
        assert (state.mass_kg_low, state.mass_kg_high) == (
            baseline.mass_kg_low, baseline.mass_kg_high
        )
        assert state.mass_kg_low <= state.mass_kg_high
