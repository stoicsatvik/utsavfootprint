from datetime import UTC, datetime, timedelta

from utsav_sensor.fusion import build_hotspots, freshness
from utsav_sensor.models import Observation


def obs(source, lat=19.076, lon=72.8777, provenance="observed", low=10, high=20, **kw):
    return Observation(
        source_type=kw.pop("source_type", "citizen"),
        provenance=provenance,
        source_id=source,
        lat=lat,
        lon=lon,
        confidence=kw.pop("confidence", 0.8),
        mass_kg_low=low,
        mass_kg_high=high,
        materials=kw.pop("materials", {"flowers": 0.8}),
        **kw,
    )


def test_nearby_reports_fuse_but_mass_is_not_summed():
    now = datetime.now(UTC)
    hs = build_hotspots([obs("a"), obs("b", lat=19.0761, low=12, high=22)], now=now)
    assert len(hs) == 1
    assert hs[0].independent_sources == 2
    assert hs[0].mass_kg_high < 30


def test_measurement_dominates_modelled_mass():
    now = datetime.now(UTC)
    hs = build_hotspots(
        [
            obs("camera", provenance="modelled", source_type="cctv", low=100, high=300),
            obs("cleanup-scale", provenance="measured", source_type="partner", low=24, high=25),
        ],
        now=now,
    )[0]
    assert hs.mass_kg_low == 24
    assert hs.mass_kg_high == 25
    assert hs.mass_basis == "measured"


def test_same_source_replays_do_not_create_fake_independent_verification():
    hs = build_hotspots([obs("same"), obs("same", lat=19.07605)])[0]
    assert hs.independent_sources == 1


def test_freshness_halves_after_half_life():
    now = datetime.now(UTC)
    assert abs(freshness(now - timedelta(hours=4), now) - 0.5) < 1e-9
