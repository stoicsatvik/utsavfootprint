"""E174: future-dated observations must not create premature hotspots.

Synthetic clock-skew contract. A five-minute tolerance is an explicit policy
choice for small producer clock offsets, not a calibration claim.
"""
import random
from datetime import UTC, datetime, timedelta

from utsav_sensor.fusion import build_hotspots
from utsav_sensor.models import Observation

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


def report(source: str, offset: timedelta) -> Observation:
    return Observation(
        id=source,
        source_type="partner",
        provenance="measured",
        source_id=source,
        lat=19.076,
        lon=72.8777,
        observed_at=NOW + offset,
        confidence=0.9,
        mass_kg_low=10,
        mass_kg_high=20,
    )


def test_far_future_report_cannot_create_present_hotspot():
    assert build_hotspots([report("future", timedelta(days=30))], now=NOW) == []


def test_future_report_cannot_inflate_present_source_count():
    states = build_hotspots(
        [report("present", timedelta(hours=-1)), report("future", timedelta(minutes=6))],
        now=NOW,
    )
    assert len(states) == 1
    assert states[0].independent_sources == 1
    assert states[0].observation_ids == ["present"]


def test_five_minute_clock_skew_is_inclusive_and_later_reports_are_deferred():
    at_boundary = report("boundary", timedelta(minutes=5))
    outside = report("outside", timedelta(minutes=5, seconds=1))
    assert len(build_hotspots([at_boundary], now=NOW)) == 1
    assert build_hotspots([outside], now=NOW) == []
    assert len(build_hotspots([outside], now=NOW + timedelta(seconds=1))) == 1


def test_past_72_hour_boundary_remains_unchanged():
    at_boundary = report("boundary", timedelta(hours=-72))
    outside = report("outside", timedelta(hours=-72, seconds=-1))
    assert len(build_hotspots([at_boundary], now=NOW)) == 1
    assert build_hotspots([outside], now=NOW) == []


def test_200_seeded_future_offsets_do_not_leak_into_current_hotspots():
    rng = random.Random(174)
    for i in range(200):
        seconds = rng.randint(5 * 60 + 1, 365 * 24 * 3600)
        future = report(f"future-{i}", timedelta(seconds=seconds))
        assert build_hotspots([future], now=NOW) == []
