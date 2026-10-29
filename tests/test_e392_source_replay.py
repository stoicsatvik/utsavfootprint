"""E392: identical same-source replays must not manufacture new fusion evidence.

Synthetic adversarial fixtures only. These tests do not establish physical pile
identity, independent sensor calibration, or field accuracy.
"""

from datetime import UTC, datetime

import pytest

from utsav_sensor.fusion import fuse_cluster
from utsav_sensor.models import Observation

NOW = datetime(2026, 10, 29, 12, tzinfo=UTC)


def observation(source: str, index: int, latitude: float, material: float, mass: float) -> Observation:
    return Observation(
        id=f"{source}-{index:03d}",
        source_type="citizen",
        provenance="observed",
        source_id=source,
        observed_at=NOW,
        ingested_at=NOW,
        lat=latitude,
        lon=72.8777,
        confidence=0.8,
        media_quality=1.0,
        materials={"plastic": material},
        mass_kg_low=mass,
        mass_kg_high=mass + 2,
    )


def test_identical_replay_cannot_shift_mass_median():
    original = [
        observation("a", 0, 19.07600, 0.0, 10),
        observation("b", 0, 19.07605, 0.5, 20),
        observation("c", 0, 19.07610, 1.0, 30),
    ]
    baseline = fuse_cluster(original, NOW)
    replayed = fuse_cluster(
        original + [observation("c", i, 19.07610, 1.0, 30) for i in range(1, 9)],
        NOW,
    )
    assert baseline.mass_kg_low == 20
    assert baseline.mass_kg_high == 22
    assert replayed.mass_kg_low == baseline.mass_kg_low
    assert replayed.mass_kg_high == baseline.mass_kg_high
    assert replayed.independent_sources == baseline.independent_sources == 3


def test_identical_replay_cannot_shift_material_or_centroid():
    original = [
        observation("a", 0, 19.07600, 0.0, 10),
        observation("b", 0, 19.07605, 0.5, 20),
        observation("c", 0, 19.07610, 1.0, 30),
    ]
    baseline = fuse_cluster(original, NOW)
    replayed = fuse_cluster(
        original + [observation("c", i, 19.07610, 1.0, 30) for i in range(1, 9)],
        NOW,
    )
    assert baseline.materials["plastic"] == pytest.approx(0.5)
    assert replayed.materials == baseline.materials
    assert replayed.lat == pytest.approx(baseline.lat, abs=1e-12)
    assert replayed.lon == pytest.approx(baseline.lon, abs=1e-12)
    assert replayed.confidence == pytest.approx(baseline.confidence, abs=1e-12)
