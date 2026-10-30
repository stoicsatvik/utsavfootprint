"""E428: fused mass outputs must be finite, nonnegative, ordered intervals."""

import json
import math
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from utsav_sensor.models import HotspotState


def state_payload(**mass_fields: float | None) -> dict:
    return {
        "id": "hs_e428",
        "lat": 19.076,
        "lon": 72.8777,
        "status": "open",
        "observation_count": 1,
        "independent_sources": 1,
        "last_observed_at": datetime(2026, 10, 30, tzinfo=UTC),
        "freshness": 1.0,
        "confidence": 0.8,
        "materials": {},
        "unresolved_hours": 1.0,
        "observation_ids": ["e428"],
        **mass_fields,
    }


@pytest.mark.parametrize(
    "bad_value",
    [float("nan"), float("inf"), float("-inf"), -1.0],
)
@pytest.mark.parametrize("field", ["mass_kg_low", "mass_kg_high"])
def test_reject_nonfinite_or_negative_fused_mass(field: str, bad_value: float) -> None:
    with pytest.raises(ValidationError):
        HotspotState.model_validate(state_payload(**{field: bad_value}))


def test_reject_inverted_fused_mass_interval() -> None:
    with pytest.raises(ValidationError, match="mass_kg_low cannot exceed mass_kg_high"):
        HotspotState.model_validate(state_payload(mass_kg_low=11.0, mass_kg_high=10.0))


@pytest.mark.parametrize(
    ("low", "high"),
    [(None, None), (None, 10.0), (0.0, 0.0), (10.0, 10.0), (10.0, 1e308)],
)
def test_valid_finite_mass_output_roundtrips(
    low: float | None, high: float | None
) -> None:
    state = HotspotState.model_validate(
        state_payload(mass_kg_low=low, mass_kg_high=high)
    )
    encoded = json.loads(state.model_dump_json())
    assert encoded["mass_kg_low"] == low
    assert encoded["mass_kg_high"] == high
    assert all(
        value is None or math.isfinite(value)
        for value in (state.mass_kg_low, state.mass_kg_high)
    )
