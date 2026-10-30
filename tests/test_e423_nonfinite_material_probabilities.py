"""E423: non-finite material probabilities must not enter evidence fusion.

The original v < 0 or v > 1 check accepted NaN because both comparisons
are false, and Pydantic serialized that value as JSON null.
"""

import math

import pytest
from pydantic import ValidationError

from utsav_sensor.fusion import build_hotspots
from utsav_sensor.models import Observation


def _observation(materials: dict[str, float]) -> Observation:
    return Observation(
        source_type="citizen",
        provenance="observed",
        source_id="synthetic-e423",
        lat=19.076,
        lon=72.8777,
        materials=materials,
    )


@pytest.mark.parametrize("invalid", [math.nan, math.inf, -math.inf, -0.01, 1.01])
def test_nonfinite_and_out_of_range_materials_are_rejected(invalid: float) -> None:
    with pytest.raises(ValidationError, match="material probabilities must be finite"):
        _observation({"flowers": invalid})


def test_nan_text_coercion_cannot_bypass_validation() -> None:
    with pytest.raises(ValidationError, match="material probabilities must be finite"):
        Observation.model_validate(
            {
                "source_type": "citizen",
                "provenance": "observed",
                "source_id": "synthetic-e423",
                "lat": 19.076,
                "lon": 72.8777,
                "materials": {"flowers": "NaN"},
            }
        )


def test_finite_boundary_values_remain_serializable_and_fusible() -> None:
    obs = _observation({"flowers": 0.0, "plastic": 1.0, "paper": 0.5})
    assert obs.materials == {"flowers": 0.0, "plastic": 1.0, "paper": 0.5}
    assert '"materials":{"flowers":0.0,"plastic":1.0,"paper":0.5}' in obs.model_dump_json()
    hotspot = build_hotspots([obs])[0]
    assert hotspot.materials == {"flowers": 0.0, "plastic": 1.0, "paper": 0.5}
