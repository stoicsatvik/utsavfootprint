"""E424: non-finite mass intervals must not enter hotspot fusion.

Pydantic Field(ge=0) rejects negative mass and NaN but permits +Infinity,
which serializes as JSON null and contaminates waste-hour metrics.
"""

import math

import pytest
from pydantic import ValidationError

from utsav_sensor.fusion import build_hotspots
from utsav_sensor.models import Observation


def _observation(**mass: float | str | None) -> Observation:
    return Observation(
        source_type="citizen",
        provenance="observed",
        source_id="synthetic-e424",
        lat=19.076,
        lon=72.8777,
        **mass,
    )


@pytest.mark.parametrize("field", ["mass_kg_low", "mass_kg_high"])
@pytest.mark.parametrize("invalid", [math.inf, "Infinity"])
def test_positive_infinite_mass_is_rejected(field: str, invalid: float | str) -> None:
    with pytest.raises(ValidationError):
        _observation(**{field: invalid})


@pytest.mark.parametrize("field", ["mass_kg_low", "mass_kg_high"])
def test_nan_and_negative_mass_stay_rejected(field: str) -> None:
    for invalid in (math.nan, -math.inf, -0.01):
        with pytest.raises(ValidationError):
            _observation(**{field: invalid})


def test_finite_mass_interval_serializes_and_fuses_without_null() -> None:
    observation = _observation(mass_kg_low=0.0, mass_kg_high=25.5)
    serialized = observation.model_dump_json()
    assert '"mass_kg_low":0.0' in serialized
    assert '"mass_kg_high":25.5' in serialized
    hotspot = build_hotspots([observation])[0]
    assert hotspot.mass_kg_low == 0.0
    assert hotspot.mass_kg_high == 25.5
    assert math.isfinite(hotspot.unresolved_waste_hours_high)


def test_missing_mass_interval_remains_allowed() -> None:
    observation = _observation()
    assert observation.mass_kg_low is None
    assert observation.mass_kg_high is None
