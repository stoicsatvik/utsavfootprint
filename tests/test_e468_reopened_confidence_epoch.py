"""E468: synthetic current-episode confidence isolation after declared cleanup.

This does not authenticate provenance, prove physical cleanup, or estimate field accuracy.
"""
from datetime import UTC, datetime, timedelta

import pytest

from utsav_sensor.fusion import fuse_cluster, observation_strength
from utsav_sensor.models import Observation

NOW = datetime(2026, 11, 1, tzinfo=UTC)
OLD = NOW - timedelta(hours=3)
CLOSED = NOW - timedelta(hours=2)
NEW = NOW - timedelta(hours=1)


def report(name, when, *, source_id=None, provenance="observed",
           confidence=0.8, status="open"):
    return Observation(
        id=name,
        source_id=source_id or name,
        source_type="partner" if provenance == "measured" else "citizen",
        provenance=provenance,
        lat=19.076,
        lon=72.8777,
        observed_at=when,
        ingested_at=when,
        confidence=confidence,
        status=status,
    )


def test_reopened_confidence_excludes_strong_old_measured_report():
    old = report("old", OLD, provenance="measured", confidence=1.0)
    closed = report("closed", CLOSED, provenance="verified_official",
                    confidence=0.0, status="cleaned")
    current = report("current", NEW, confidence=0.05)
    result = fuse_cluster([old, closed, current], NOW)
    expected = observation_strength(current, NOW)
    legacy = 1 - (1 - observation_strength(old, NOW)) * (1 - expected)
    assert legacy > 17 * expected  # Previously a large false confidence boost.
    assert result.status == "open"
    assert result.confidence == pytest.approx(expected, abs=1e-12)
    assert result.independent_sources == 3  # Audit counts remain historical.


def test_closed_hotspot_retains_historical_confidence():
    old = report("old", OLD, provenance="measured", confidence=1.0)
    closed = report("closed", CLOSED, provenance="verified_official",
                    confidence=0.0, status="cleaned")
    result = fuse_cluster([old, closed], NOW)
    assert result.status == "cleaned"
    assert result.confidence == pytest.approx(observation_strength(old, NOW))


def test_unverified_cleanup_does_not_reset_confidence():
    old = report("old", OLD, provenance="measured", confidence=1.0)
    unverified = report("unverified", CLOSED, status="cleaned", confidence=0.0)
    current = report("current", NEW, confidence=0.05)
    result = fuse_cluster([old, unverified, current], NOW)
    a = observation_strength(old, NOW)
    b = observation_strength(current, NOW)
    assert result.confidence == pytest.approx(1 - (1 - a) * (1 - b))


def test_reused_source_keeps_only_post_cleanup_confidence():
    old = report("old", OLD, source_id="shared",
                 provenance="measured", confidence=1.0)
    closed = report("closed", CLOSED, provenance="verified_official",
                    confidence=0.0, status="cleaned")
    current = report("current", NEW, source_id="shared", confidence=0.05)
    result = fuse_cluster([old, closed, current], NOW)
    assert result.confidence == pytest.approx(observation_strength(current, NOW))
    assert result.independent_sources == 2


def test_equal_time_reopening_abstains_without_later_confidence():
    old = report("old", OLD, provenance="measured", confidence=1.0)
    closed = report("closed", CLOSED, provenance="verified_official",
                    confidence=0.0, status="cleaned")
    ambiguous = report("ambiguous", CLOSED, confidence=0.8)
    result = fuse_cluster([old, closed, ambiguous], NOW)
    assert result.status == "open"
    assert result.confidence == 0.0
    assert result.independent_sources == 3
