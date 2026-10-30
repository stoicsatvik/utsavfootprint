from datetime import UTC, datetime, timedelta

import pytest

from utsav_sensor.history import (
    ObservationRevision,
    build_hotspots_from_revisions_as_of,
    replay_observation_revisions,
)
from utsav_sensor.models import Observation

BASE = datetime(2026, 10, 30, 0, 0, tzinfo=UTC)


def hour(n):
    return BASE + timedelta(hours=n)


def observation(record_id, observed, ingested, status="open", provenance="observed"):
    return Observation(
        id=record_id,
        source_type="partner" if provenance == "measured" else "citizen",
        provenance=provenance,
        source_id=record_id,
        lat=19.076,
        lon=72.8777,
        observed_at=hour(observed),
        ingested_at=hour(ingested),
        status=status,
        confidence=0.8,
    )


def test_late_correction_cannot_rewrite_prior_snapshot():
    original = observation("site", 4, 5)
    correction = observation("site", 6, 7, "cleaned", "measured")
    log = [
        ObservationRevision(1, hour(5), "site", original),
        ObservationRevision(2, hour(10), "site", correction),
    ]
    assert replay_observation_revisions(log, hour(8))[0].status == "open"
    assert replay_observation_revisions(log, hour(11))[0].status == "cleaned"
    assert build_hotspots_from_revisions_as_of(log, hour(8))[0].status == "open"
    assert build_hotspots_from_revisions_as_of(log, hour(11))[0].status == "cleaned"


def test_deletion_tombstone_only_affects_future_snapshots():
    log = [
        ObservationRevision(1, hour(5), "site", observation("site", 4, 5)),
        ObservationRevision(2, hour(12), "site", None),
    ]
    assert len(replay_observation_revisions(log, hour(11))) == 1
    assert replay_observation_revisions(log, hour(12)) == []
    assert build_hotspots_from_revisions_as_of(log, hour(13)) == []


def test_equal_receipt_timestamps_use_sequence_not_input_order():
    log = [
        ObservationRevision(2, hour(7), "site", observation("site", 6, 7, "claimed")),
        ObservationRevision(1, hour(7), "site", observation("site", 4, 5)),
    ]
    assert replay_observation_revisions(log, hour(7))[0].status == "claimed"


def test_invalid_log_fails_closed():
    first = ObservationRevision(1, hour(5), "site", observation("site", 4, 5))
    cases = [
        [first, first],
        [first, ObservationRevision(2, hour(4), "site", None)],
        [first, ObservationRevision(3, hour(7), "site", None)],
        [ObservationRevision(2, hour(5), "site", observation("site", 4, 5))],
        [ObservationRevision(1, hour(5), "other", observation("site", 4, 5))],
        [ObservationRevision(0, hour(5), "site", observation("site", 4, 5))],
        [ObservationRevision(1, hour(5), "site", observation("site", 4, 6))],
    ]
    for case in cases:
        with pytest.raises(ValueError):
            replay_observation_revisions(case, hour(8))
    with pytest.raises(ValueError):
        replay_observation_revisions([first], datetime(2026, 10, 30))


def test_replay_returns_independent_copy_without_mutating_log():
    original = observation("site", 4, 5)
    log = [ObservationRevision(1, hour(5), "site", original)]
    result = replay_observation_revisions(log, hour(8))
    result[0].status = "cleaned"
    assert original.status == "open"
    assert replay_observation_revisions(log, hour(8))[0].status == "open"
