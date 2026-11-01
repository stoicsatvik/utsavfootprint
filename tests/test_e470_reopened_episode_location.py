"""E470 synthetic diagnostic contracts, not physical cleanup or field validation."""
from datetime import UTC, datetime, timedelta

import pytest

from utsav_sensor.episode_location import reopened_episode_location
from utsav_sensor.fusion import haversine_m
from utsav_sensor.models import Observation

NOW = datetime(2026, 11, 1, tzinfo=UTC)
OLD = NOW - timedelta(hours=3)
CLOSED = NOW - timedelta(hours=2)
NEW = NOW - timedelta(hours=1)


def report(name, when, *, lat=19.076, lon=72.8777, source=None,
           provenance="observed", status="open", confidence=0.8):
    return Observation(
        id=name, source_id=source or name,
        source_type="partner" if provenance == "measured" else "citizen",
        provenance=provenance, lat=lat, lon=lon, observed_at=when,
        ingested_at=when, confidence=confidence, status=status,
    )


def closed():
    return report("cleanup", CLOSED, provenance="verified_official",
                  status="cleaned", confidence=0.0)


def test_old_high_strength_cannot_shift_reopened_candidate():
    old = report("old", OLD, confidence=1.0, provenance="measured")
    new = report("new", NEW, lon=72.8786, confidence=0.05)
    actual = reopened_episode_location([old, closed(), new], NOW)
    assert actual is not None
    assert haversine_m(*actual, new.lat, new.lon) < 1e-6


def test_no_declared_cleanup_has_no_separate_episode_coordinate():
    assert reopened_episode_location([report("old", OLD), report("new", NEW)], NOW) is None


def test_unverified_cleanup_cannot_reset_location():
    unverified = report("citizen-claim", CLOSED, status="cleaned")
    assert reopened_episode_location([report("old", OLD), unverified,
                                      report("new", NEW)], NOW) is None


def test_closed_hotspot_has_no_current_pile_coordinate():
    assert reopened_episode_location([report("old", OLD), closed()], NOW) is None


def test_equal_time_open_and_cleanup_abstains():
    same_time = report("same", CLOSED, confidence=1.0)
    assert reopened_episode_location([report("old", OLD), closed(), same_time], NOW) is None


def test_zero_strength_post_cleanup_abstains():
    assert reopened_episode_location([report("old", OLD), closed(),
                                      report("new", NEW, confidence=0)], NOW) is None


def test_reused_source_is_reselected_within_current_episode():
    old = report("old", OLD, source="same", provenance="measured", confidence=1.0)
    new = report("new", NEW, source="same", lon=72.8786, confidence=0.05)
    actual = reopened_episode_location([old, closed(), new], NOW)
    assert actual is not None
    assert haversine_m(*actual, new.lat, new.lon) < 1e-6


def test_newest_credible_cleanup_resets_again():
    first = report("interim", NEW, lon=72.8786)
    second_cleanup = report("second", NOW - timedelta(minutes=45),
                            provenance="measured", status="verified")
    latest = report("latest", NOW - timedelta(minutes=15), lon=72.879)
    actual = reopened_episode_location([report("old", OLD), closed(), first,
                                        second_cleanup, latest], NOW)
    assert actual is not None
    assert haversine_m(*actual, latest.lat, latest.lon) < 1e-6


def test_future_report_fails_closed():
    future = report("future", NOW + timedelta(minutes=6))
    with pytest.raises(ValueError, match="future-dated"):
        reopened_episode_location([report("old", OLD), closed(), future], NOW)


def test_empty_cluster_rejected():
    with pytest.raises(ValueError, match="empty cluster"):
        reopened_episode_location([], NOW)


def test_dateline_current_episode_stays_near_seam():
    old = report("old", OLD, lat=0, lon=179.999, provenance="measured")
    cleanup = report("cleanup", CLOSED, lat=0, lon=179.999,
                     provenance="verified_official", status="cleaned")
    a = report("a", NEW, lat=0, lon=179.9998)
    b = report("b", NEW, lat=0, lon=-179.9998)
    actual = reopened_episode_location([old, cleanup, a, b], NOW)
    assert actual is not None
    assert abs(abs(actual[1]) - 180) < 0.001


def test_current_location_is_order_invariant():
    reports = [report("old", OLD, confidence=1.0, provenance="measured"),
               closed(), report("a", NEW, lon=72.8785),
               report("b", NEW, lon=72.8787)]
    assert reopened_episode_location(reports, NOW) == pytest.approx(
        reopened_episode_location(list(reversed(reports)), NOW)
    )
