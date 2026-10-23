"""E188: a future-dated ingestion must not certify a source as live.

Synthetic, frozen-clock checks. Five minutes is the existing observation
clock-skew policy, not a measured sensor synchronization guarantee.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from utsav_sensor.engine import SensorEngine
from utsav_sensor.models import Observation

NOW = datetime(2026, 10, 24, 0, 0, tzinfo=UTC)


def report(source: str, ingested_at: datetime) -> Observation:
    return Observation(
        id=source,
        source_type="partner",
        provenance="observed",
        source_id=source,
        lat=19.076,
        lon=72.8777,
        observed_at=NOW,
        ingested_at=ingested_at,
    )


def freeze_clock(monkeypatch, value: datetime) -> None:
    class FixedDatetime:
        @staticmethod
        def now(tz):
            assert tz == UTC
            return value

    monkeypatch.setattr("utsav_sensor.engine.datetime", FixedDatetime)


@pytest.mark.asyncio
async def test_future_ingestion_is_not_live(monkeypatch):
    freeze_clock(monkeypatch, NOW)
    engine = SensorEngine()
    await engine.ingest(report("future", NOW + timedelta(days=30)))
    state = (await engine.source_health())[0]
    assert state.state == "clock_skew"
    assert state.age_seconds == 0.0


@pytest.mark.asyncio
async def test_six_minutes_ahead_is_not_live(monkeypatch):
    freeze_clock(monkeypatch, NOW)
    engine = SensorEngine()
    await engine.ingest(report("ahead", NOW + timedelta(minutes=6)))
    assert (await engine.source_health())[0].state == "clock_skew"


@pytest.mark.asyncio
async def test_five_minute_tolerance_stays_live(monkeypatch):
    freeze_clock(monkeypatch, NOW)
    engine = SensorEngine()
    await engine.ingest(report("boundary", NOW + timedelta(minutes=5)))
    state = (await engine.source_health())[0]
    assert state.state == "live"
    assert state.age_seconds == 0.0


@pytest.mark.asyncio
async def test_past_ingestion_remains_stale(monkeypatch):
    freeze_clock(monkeypatch, NOW)
    engine = SensorEngine()
    await engine.ingest(report("old", NOW - timedelta(hours=2)))
    state = (await engine.source_health())[0]
    assert state.state == "stale"
    assert state.age_seconds == 7200.0
