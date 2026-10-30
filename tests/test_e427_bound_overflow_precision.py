"""E427: distinguish per-bound overflow from absent mass in Prometheus."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from utsav_sensor import api
from utsav_sensor.fusion import build_hotspots
from utsav_sensor.models import HotspotState, Observation

NOW = datetime(2026, 10, 30, 10, tzinfo=UTC)


def observation(low: float | None, high: float | None) -> Observation:
    return Observation(
        source_type="citizen",
        provenance="observed",
        source_id="e427-source",
        lat=19.076,
        lon=72.8777,
        observed_at=NOW - timedelta(hours=2),
        ingested_at=NOW - timedelta(hours=1),
        mass_kg_low=low,
        mass_kg_high=high,
    )


def test_fusion_exposes_exact_overflowed_bound_in_json() -> None:
    state = build_hotspots([observation(10.0, 1e308)], now=NOW)[0]
    assert state.unresolved_waste_hours_low == 20.0
    assert state.unresolved_waste_hours_high is None
    assert state.unresolved_waste_hours_overflow is True
    assert state.unresolved_waste_hours_overflow_low is False
    assert state.unresolved_waste_hours_overflow_high is True
    encoded = json.loads(state.model_dump_json())
    assert encoded["unresolved_waste_hours_overflow_low"] is False
    assert encoded["unresolved_waste_hours_overflow_high"] is True


def test_fusion_missing_mass_is_not_overflow() -> None:
    state = build_hotspots([observation(None, None)], now=NOW)[0]
    assert state.unresolved_waste_hours_overflow is False
    assert state.unresolved_waste_hours_overflow_low is False
    assert state.unresolved_waste_hours_overflow_high is False


def test_prometheus_keeps_known_low_total_when_other_high_bound_overflows(
    monkeypatch,
) -> None:
    ordinary = build_hotspots([observation(10.0, 20.0)], now=NOW)[0]
    # Synthetic partial-bound output: low evidence absent, high product overflow.
    mixed = HotspotState.model_validate(
        {
            **ordinary.model_dump(),
            "mass_kg_low": None,
            "mass_kg_high": 1e308,
            "unresolved_waste_hours_low": None,
            "unresolved_waste_hours_high": None,
            "unresolved_waste_hours_overflow": True,
            "unresolved_waste_hours_overflow_low": False,
            "unresolved_waste_hours_overflow_high": True,
        }
    )

    async def hotspots():
        return [ordinary, mixed]

    async def observations():
        return []

    monkeypatch.setattr(api.engine, "hotspots", hotspots)
    monkeypatch.setattr(api.engine, "observations", observations)
    output = asyncio.run(api.metrics())
    assert "utsav_unresolved_waste_hours_low 20.0" in output
    assert "utsav_unresolved_waste_hours_high NaN" in output
    assert "utsav_unresolved_waste_hours_overflow_hotspots 1" in output


def test_legacy_aggregate_only_flag_remains_conservative(monkeypatch) -> None:
    ordinary = build_hotspots([observation(10.0, 20.0)], now=NOW)[0]
    legacy = ordinary.model_dump(
        exclude={
            "unresolved_waste_hours_overflow_low",
            "unresolved_waste_hours_overflow_high",
        }
    )
    legacy.update(
        unresolved_waste_hours_low=None,
        unresolved_waste_hours_high=None,
        unresolved_waste_hours_overflow=True,
    )
    state = HotspotState.model_validate(legacy)
    assert state.unresolved_waste_hours_overflow_low is None
    assert state.unresolved_waste_hours_overflow_high is None

    async def hotspots():
        return [state]

    async def observations():
        return []

    monkeypatch.setattr(api.engine, "hotspots", hotspots)
    monkeypatch.setattr(api.engine, "observations", observations)
    output = asyncio.run(api.metrics())
    assert "utsav_unresolved_waste_hours_low NaN" in output
    assert "utsav_unresolved_waste_hours_high NaN" in output


@pytest.mark.parametrize(
    "changes",
    [
        {"unresolved_waste_hours_overflow_low": True},
        {
            "unresolved_waste_hours_overflow": True,
            "unresolved_waste_hours_overflow_low": False,
            "unresolved_waste_hours_overflow_high": False,
        },
        {
            "unresolved_waste_hours_overflow": True,
            "unresolved_waste_hours_overflow_low": True,
            "unresolved_waste_hours_overflow_high": False,
        },
    ],
)
def test_inconsistent_overflow_flags_are_rejected(changes: dict) -> None:
    ordinary = build_hotspots([observation(10.0, 20.0)], now=NOW)[0]
    with pytest.raises(ValidationError):
        HotspotState.model_validate({**ordinary.model_dump(), **changes})
