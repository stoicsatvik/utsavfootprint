"""E172: identical mass-interval claims from one source are not independent evidence.

Synthetic software-contract tests. A distinct report ID is not an independent
mass measurement when the same source repeats an identical interval.
"""

import random
from datetime import UTC, datetime

from utsav_sensor.fusion import fuse_cluster
from utsav_sensor.models import Observation

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


def report(source: str, low: float, high: float, oid: str) -> Observation:
    return Observation(
        id=oid,
        source_type="partner",
        provenance="measured",
        source_id=source,
        lat=19.076,
        lon=72.8777,
        observed_at=NOW,
        mass_kg_low=low,
        mass_kg_high=high,
    )


def mass(reports: list[Observation]) -> tuple[float, float]:
    state = fuse_cluster(reports, now=NOW)
    return state.mass_kg_low, state.mass_kg_high


def test_replaying_one_of_two_distinct_source_claims_does_not_shift_mass():
    original = [
        report("A", 100, 110, "a1"),
        report("A", 200, 210, "a2"),
        report("B", 300, 310, "b1"),
    ]
    assert mass(original) == (225.0, 235.0)
    replayed = original + [
        report("A", 200, 210, f"a-replay-{i}") for i in range(100)
    ]
    assert mass(replayed) == mass(original)


def test_new_distinct_source_claim_may_change_estimate():
    original = [
        report("A", 100, 110, "a1"),
        report("A", 200, 210, "a2"),
        report("B", 300, 310, "b1"),
    ]
    new_claim = report("A", 400, 410, "a3")
    assert mass(original + [new_claim]) == (250.0, 260.0)


def test_randomized_same_source_mass_claim_replay_and_permutation():
    rng = random.Random(172)
    for trial in range(200):
        a1 = rng.randint(0, 100)
        a2 = a1 + rng.randint(1, 100)
        b = a2 + rng.randint(1, 100)
        original = [
            report("A", a1, a1 + 10, f"a1-{trial}"),
            report("A", a2, a2 + 10, f"a2-{trial}"),
            report("B", b, b + 10, f"b-{trial}"),
        ]
        expected = mass(original)
        choice = rng.choice(original[:2])
        replayed = original + [
            report("A", choice.mass_kg_low, choice.mass_kg_high, f"dup-{trial}-{i}")
            for i in range(rng.randint(1, 25))
        ]
        rng.shuffle(replayed)
        assert mass(replayed) == expected
