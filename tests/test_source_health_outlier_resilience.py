"""E192: a future ingestion outlier must not mask otherwise valid source health.

All inputs are synthetic and clocks are frozen. The source ID is not
authenticated, so this tests resilience within one declared source, not
identity security or genuine server-side ingestion provenance.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from utsav_sensor.engine import SensorEngine
from utsav_sensor.models import Observation

NOW = datetime(2026, 10, 24, 0, 0, tzinfo=UTC)


def report(record_id: str, when: datetime) -> Observation:
    return Observation(
        id=record_id,
        source_type="partner",
        provenance="observed",
        source_id="same-source",
        lat=19.076,
        lon=72.8777,
        observed_at=NOW,
        ingested_at=when,
    )


def freeze_clock(monkeypatch) -> None:
    class FixedDatetime:
        @staticmethod
        def now(tz):
            assert tz == UTC
            return NOW

    monkeypatch.setattr("utsav_sensor.engine.datetime", FixedDatetime)


@pytest.mark.asyncio
async def test_future_outlier_does_not_mask_live_source(monkeypatch):
    freeze_clock(monkeypatch)
    engine = SensorEngine()
    valid_time = NOW - timedelta(minutes=2)
    await engine.ingest(report("valid", valid_time))
    await engine.ingest(report("outlier", NOW + timedelta(days=30)))

    state = (await engine.source_health())[0]
    assert state.state == "live"
    assert state.last_ingested_at == valid_time
    assert state.age_seconds == 120.0
    assert state.observation_count == 2
    assert state.clock_skew_count == 1


@pytest.mark.asyncio
async def test_future_outlier_does_not_mask_stale_source(monkeypatch):
    freeze_clock(monkeypatch)
    engine = SensorEngine()
    valid_time = NOW - timedelta(hours=2)
    await engine.ingest(report("stale", valid_time))
    await engine.ingest(report("outlier", NOW + timedelta(minutes=6)))

    state = (await engine.source_health())[0]
    assert state.state == "stale"
    assert state.last_ingested_at == valid_time
    assert state.age_seconds == 7200.0
    assert state.clock_skew_count == 1


@pytest.mark.asyncio
async def test_all_future_reports_remain_explicitly_flagged(monkeypatch):
    freeze_clock(monkeypatch)
    engine = SensorEngine()
    await engine.ingest(report("future-1", NOW + timedelta(minutes=6)))
    await engine.ingest(report("future-2", NOW + timedelta(days=30)))

    state = (await engine.source_health())[0]
    assert state.state == "clock_skew"
    assert state.last_ingested_at == NOW + timedelta(days=30)
    assert state.age_seconds == 0.0
    assert state.observation_count == 2
    assert state.clock_skew_count == 2


@pytest.mark.asyncio
async def test_skew_boundary_and_clean_source_control(monkeypatch):
    freeze_clock(monkeypatch)
    engine = SensorEngine()
    boundary = NOW + timedelta(minutes=5)
    await engine.ingest(report("boundary", boundary))
    await engine.ingest(report("outlier", NOW + timedelta(minutes=6)))

    state = (await engine.source_health())[0]
    assert state.state == "live"
    assert state.last_ingested_at == boundary
    assert state.clock_skew_count == 1

    clean = SensorEngine()
    await clean.ingest(report("normal", NOW - timedelta(seconds=10)))
    clean_state = (await clean.source_health())[0]
    assert clean_state.state == "live"
    assert clean_state.clock_skew_count == 0
