from datetime import UTC, datetime, timedelta

import pytest

from utsav_sensor.calibration import CalibrationPair, evaluate_calibration
from utsav_sensor.models import Observation, Provenance, SourceType


T0 = datetime(2026, 9, 18, 10, tzinfo=UTC)


def obs(*, oid: str, source_id: str, provenance: Provenance, confidence: float = 0.5,
        status: str = "open", low: float | None = None, high: float | None = None,
        minutes: int = 0, external_ref: str | None = None) -> Observation:
    return Observation(
        id=oid, source_type=SourceType.PARTNER, provenance=provenance,
        source_id=source_id, lat=19.1, lon=72.9,
        observed_at=T0 + timedelta(minutes=minutes), confidence=confidence,
        status=status, mass_kg_low=low, mass_kg_high=high, external_ref=external_ref,
    )


def reference(**kwargs) -> Observation:
    return obs(provenance=Provenance.MEASURED, minutes=10, external_ref="ledger:ref-1", **kwargs)


def test_requires_traceable_later_authoritative_reference():
    claim = obs(oid="c", source_id="citizen-1", provenance=Provenance.OBSERVED)
    weak = obs(oid="r", source_id="model-1", provenance=Provenance.MODELLED, minutes=10, external_ref="x")
    with pytest.raises(ValueError, match="measured or verified_official"):
        CalibrationPair(claim, weak)

    untraceable = obs(oid="r2", source_id="partner", provenance=Provenance.MEASURED, minutes=10)
    with pytest.raises(ValueError, match="external_ref"):
        CalibrationPair(claim, untraceable)


def test_repeated_source_cannot_manufacture_independence():
    ref = reference(oid="r", source_id="scale", low=10, high=10)
    pairs = [
        CalibrationPair(obs(oid="c1", source_id="same-camera", provenance=Provenance.MODELLED, confidence=0.8, low=8, high=12), ref),
        CalibrationPair(obs(oid="c2", source_id="same-camera", provenance=Provenance.MODELLED, confidence=0.8, low=9, high=11), ref),
    ]
    metrics = evaluate_calibration(pairs)
    assert metrics.pair_count == 2
    assert metrics.independent_source_count == 1
    assert metrics.empirical_accuracy == 1.0
    assert metrics.brier_score == pytest.approx(0.04)


def test_metrics_report_error_without_reweighting_claims():
    claim = obs(oid="c", source_id="observer", provenance=Provenance.OBSERVED, confidence=0.9, low=4, high=6)
    ref = reference(oid="r", source_id="scale", status="cleaned", low=0, high=0)
    before = claim.model_dump()
    metrics = evaluate_calibration([CalibrationPair(claim, ref)])
    assert metrics.empirical_accuracy == 0.0
    assert metrics.brier_score == pytest.approx(0.81)
    assert metrics.mass_midpoint_rmse_kg == pytest.approx(5.0)
    assert claim.model_dump() == before
