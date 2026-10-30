"""E426: finite inputs must never silently become infinite hotspot metrics."""

import asyncio
import json
import math
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from utsav_sensor import api
from utsav_sensor.fusion import build_hotspots
from utsav_sensor.models import HotspotState, Observation

NOW = datetime(2026, 10, 30, 10, tzinfo=UTC)


def observation(source: str, low: float | None, high: float | None, **kw) -> Observation:
    return Observation(
        source_type="citizen",
        provenance=kw.pop("provenance", "observed"),
        source_id=source,
        lat=19.076,
        lon=72.8777,
        observed_at=NOW - timedelta(hours=2),
        ingested_at=NOW - timedelta(hours=1),
        mass_kg_low=low,
        mass_kg_high=high,
        **kw,
    )


def test_large_finite_mass_flags_product_overflow_without_losing_evidence() -> None:
    hotspot = build_hotspots([observation("huge", 10.0, 1e308)], now=NOW)[0]
    assert hotspot.mass_kg_high == 1e308
    assert hotspot.unresolved_waste_hours_low == 20.0
    assert hotspot.unresolved_waste_hours_high is None
    assert hotspot.unresolved_waste_hours_overflow is True
    output = json.loads(hotspot.model_dump_json())
    assert output["mass_kg_high"] == 1e308
    assert output["unresolved_waste_hours_high"] is None
    assert output["unresolved_waste_hours_overflow"] is True


def test_even_median_of_large_finite_mass_stays_finite() -> None:
    hotspot = build_hotspots(
        [observation("one", 1e308, 1e308), observation("two", 1e308, 1e308)],
        now=NOW,
    )[0]
    assert hotspot.mass_kg_low == 1e308
    assert hotspot.mass_kg_high == 1e308
    assert hotspot.unresolved_waste_hours_overflow is True


def test_zero_unresolved_duration_does_not_flag_overflow() -> None:
    hotspot = build_hotspots(
        [observation("measured-cleanup", 1e308, 1e308, provenance="measured", status="cleaned")],
        now=NOW,
    )[0]
    assert hotspot.unresolved_hours == 0.0
    assert hotspot.unresolved_waste_hours_high == 0.0
    assert hotspot.unresolved_waste_hours_overflow is False


def test_ordinary_mass_hours_and_missing_mass_remain_distinct() -> None:
    ordinary = build_hotspots([observation("ordinary", 10.0, 20.0)], now=NOW)[0]
    assert ordinary.unresolved_waste_hours_low == 20.0
    assert ordinary.unresolved_waste_hours_high == 40.0
    assert ordinary.unresolved_waste_hours_overflow is False

    missing = build_hotspots([observation("missing", None, None)], now=NOW)[0]
    assert missing.unresolved_waste_hours_high is None
    assert missing.unresolved_waste_hours_overflow is False


def test_output_schema_rejects_nonfinite_derived_metric() -> None:
    hotspot = build_hotspots([observation("normal", 10.0, 20.0)], now=NOW)[0]
    with pytest.raises(ValidationError):
        HotspotState.model_validate(
            {**hotspot.model_dump(), "unresolved_waste_hours_high": math.inf}
        )


def test_prometheus_does_not_count_overflowed_metric_as_zero(monkeypatch) -> None:
    overflow = build_hotspots([observation("huge", 10.0, 1e308)], now=NOW)[0]

    async def hotspots():
        return [overflow]

    async def observations():
        return []

    monkeypatch.setattr(api.engine, "hotspots", hotspots)
    monkeypatch.setattr(api.engine, "observations", observations)
    output = asyncio.run(api.metrics())
    assert "utsav_unresolved_waste_hours_low 20.0" in output
    assert "utsav_unresolved_waste_hours_high NaN" in output
    assert "utsav_unresolved_waste_hours_overflow_hotspots 1" in output


def test_prometheus_flags_aggregate_overflow_of_individually_finite_metrics(
    monkeypatch,
) -> None:
    ordinary = build_hotspots([observation("ordinary", 10.0, 20.0)], now=NOW)[0]
    huge = HotspotState.model_validate(
        {
            **ordinary.model_dump(),
            "unresolved_waste_hours_low": 1e308,
            "unresolved_waste_hours_high": 1e308,
            "unresolved_waste_hours_overflow": False,
        }
    )

    async def hotspots():
        return [huge, huge]

    async def observations():
        return []

    monkeypatch.setattr(api.engine, "hotspots", hotspots)
    monkeypatch.setattr(api.engine, "observations", observations)
    output = asyncio.run(api.metrics())
    assert "utsav_unresolved_waste_hours_low NaN" in output
    assert "utsav_unresolved_waste_hours_high NaN" in output
    assert "utsav_unresolved_waste_hours_overflow_hotspots 0" in output
