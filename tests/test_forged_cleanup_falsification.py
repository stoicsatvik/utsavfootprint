"""Falsification: producer-asserted cleanup must not be mistaken for authenticated removal.

These synthetic cases express the *desired* fail-closed contract. Current schemas
carry no server-authenticated cleanup receipt, so this is a security hypothesis,
not a claim that a modelled/observed report is necessarily fraudulent.
"""

from datetime import UTC, datetime, timedelta

import pytest

from utsav_sensor.models import Observation
from utsav_sensor.closure_auth import closure_digest
from utsav_sensor.place_query import summarize_coordinates

BASE = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
LAT, LON = 19.1947, 72.9737


def observation(oid: str, minute: int, *, status: str, provenance: str,
                source_type: str, low: float | None = None,
                high: float | None = None) -> Observation:
    return Observation(
        id=oid,
        source_id=oid,
        source_type=source_type,
        provenance=provenance,
        lat=LAT,
        lon=LON,
        observed_at=BASE + timedelta(minutes=minute),
        ingested_at=BASE + timedelta(minutes=minute),
        confidence=0.9,
        status=status,
        mass_kg_low=low,
        mass_kg_high=high,
    )


@pytest.mark.parametrize("provenance", ["modelled", "observed"])
def test_untrusted_cleanup_cannot_erase_measured_open_waste(provenance: str):
    open_mass = observation(
        "independent-mass", 0, status="open", provenance="measured",
        source_type="partner", low=100, high=120,
    )
    forged_closure = observation(
        "unauthenticated-closure", 5, status="cleaned", provenance=provenance,
        source_type="citizen",
    )
    result = summarize_coordinates(
        [open_mass, forged_closure],
        LAT,
        LON,
        radius_m=100,
        start=BASE - timedelta(minutes=1),
        end=BASE + timedelta(hours=1),
        authenticated_closure_digests=frozenset(),
    )
    # Desired policy: closure is not authoritative without an independent receipt.
    assert result.excluded_unattested_closures == 1
    assert result.current_mass_kg_low == 100
    assert result.removed_mass_kg_low == 0
    assert result.unresolved_waste_hours_low is not None
    assert result.unresolved_waste_hours_low > 0


def test_independently_attested_cleanup_can_close_the_track():
    open_mass = observation(
        "independent-mass", 0, status="open", provenance="measured",
        source_type="partner", low=100, high=120,
    )
    closure = observation(
        "attested-closure", 5, status="cleaned", provenance="observed",
        source_type="citizen",
    )
    result = summarize_coordinates(
        [open_mass, closure], LAT, LON, radius_m=100,
        start=BASE - timedelta(minutes=1),
        end=BASE + timedelta(hours=1),
        authenticated_closure_digests=frozenset({closure_digest(closure)}),
    )
    assert result.excluded_unattested_closures == 0
    assert result.current_mass_kg_low == 0
    assert result.removed_mass_kg_low == 100


def test_receipt_digest_rejects_tampered_timestamp_even_with_same_id():
    closure = observation(
        "receipt-id", 5, status="cleaned", provenance="observed",
        source_type="citizen",
    )
    tampered = closure.model_copy(update={"observed_at": BASE + timedelta(minutes=6)})
    assert closure_digest(closure) != closure_digest(tampered)
    open_mass = observation(
        "independent-mass", 0, status="open", provenance="measured",
        source_type="partner", low=100, high=120,
    )
    result = summarize_coordinates(
        [open_mass, tampered], LAT, LON, radius_m=100,
        start=BASE - timedelta(minutes=1),
        end=BASE + timedelta(hours=1),
        authenticated_closure_digests=frozenset({closure_digest(closure)}),
    )
    assert result.excluded_unattested_closures == 1
    assert result.current_mass_kg_low == 100
