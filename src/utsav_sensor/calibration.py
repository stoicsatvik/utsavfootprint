from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from .models import Observation, Provenance


@dataclass(frozen=True)
class CalibrationPair:
    """A source claim paired with a later traceable reference observation."""

    claim: Observation
    reference: Observation

    def __post_init__(self) -> None:
        if self.claim.id == self.reference.id:
            raise ValueError("claim and reference must be distinct observations")
        if self.reference.provenance not in {Provenance.MEASURED, Provenance.VERIFIED_OFFICIAL}:
            raise ValueError("reference must be measured or verified_official")
        if self.reference.observed_at < self.claim.observed_at:
            raise ValueError("reference cannot predate the claim")
        if self.reference.external_ref is None:
            raise ValueError("reference must preserve a traceable external_ref")


@dataclass(frozen=True)
class CalibrationMetrics:
    pair_count: int
    independent_source_count: int
    mean_confidence: float
    empirical_accuracy: float
    brier_score: float
    mass_midpoint_rmse_kg: float | None


def _event_present(observation: Observation) -> bool:
    return observation.status not in {"cleaned"} and (
        observation.mass_kg_high is None or observation.mass_kg_high > 0
    )


def _mass_midpoint(observation: Observation) -> float | None:
    if observation.mass_kg_low is None or observation.mass_kg_high is None:
        return None
    return (observation.mass_kg_low + observation.mass_kg_high) / 2


def evaluate_calibration(pairs: list[CalibrationPair]) -> CalibrationMetrics:
    """Evaluate frozen claims without mutating fusion/base provenance weights.

    Repeated claims from the same source_id are retained for error accounting but
    never counted as independent confirmation.
    """

    if not pairs:
        raise ValueError("at least one calibration pair is required")

    outcomes = [1.0 if _event_present(pair.reference) else 0.0 for pair in pairs]
    confidences = [pair.claim.confidence for pair in pairs]
    accuracy = sum((c >= 0.5) == bool(y) for c, y in zip(confidences, outcomes, strict=True)) / len(pairs)
    brier = sum((c - y) ** 2 for c, y in zip(confidences, outcomes, strict=True)) / len(pairs)

    mass_errors: list[float] = []
    for pair in pairs:
        claim_mass = _mass_midpoint(pair.claim)
        reference_mass = _mass_midpoint(pair.reference)
        if claim_mass is not None and reference_mass is not None:
            mass_errors.append((claim_mass - reference_mass) ** 2)

    return CalibrationMetrics(
        pair_count=len(pairs),
        independent_source_count=len({pair.claim.source_id for pair in pairs}),
        mean_confidence=sum(confidences) / len(confidences),
        empirical_accuracy=accuracy,
        brier_score=brier,
        mass_midpoint_rmse_kg=sqrt(sum(mass_errors) / len(mass_errors)) if mass_errors else None,
    )
