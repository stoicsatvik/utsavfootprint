from datetime import UTC, datetime, timedelta

from utsav_sensor.models import Observation, Provenance, SourceType
from utsav_sensor.place_query import summarize_coordinates


def make_obs(
    oid: str,
    minutes: int,
    low: float | None,
    high: float | None,
    *,
    status: str = "open",
    source: str = "s1",
    provenance: Provenance = Provenance.OBSERVED,
) -> Observation:
    base = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
    return Observation(
        id=oid,
        source_type=SourceType.CITIZEN,
        provenance=provenance,
        source_id=source,
        lat=19.1947,
        lon=72.9737,
        observed_at=base + timedelta(minutes=minutes),
        confidence=0.8,
        mass_kg_low=low,
        mass_kg_high=high,
        status=status,
    )


def test_repeated_views_do_not_sum_same_pile():
    start = datetime(2026, 9, 11, 11, 0, tzinfo=UTC)
    end = datetime(2026, 9, 11, 14, 0, tzinfo=UTC)
    summary = summarize_coordinates(
        [make_obs("a", 0, 100, 120), make_obs("b", 30, 105, 125, source="s2")],
        19.1947,
        72.9737,
        radius_m=200,
        start=start,
        end=end,
    )
    assert summary.generated_mass_kg_low == 100
    assert summary.generated_mass_kg_high == 145
    assert summary.current_mass_kg_low == 105
    assert summary.current_mass_kg_high == 125


def test_cleanup_then_new_waste_counts_new_generation():
    start = datetime(2026, 9, 11, 11, 0, tzinfo=UTC)
    end = datetime(2026, 9, 11, 16, 0, tzinfo=UTC)
    observations = [
        make_obs("a", 0, 100, 120),
        make_obs("clean", 60, None, None, status="cleaned", source="crew"),
        make_obs("b", 120, 40, 50, source="s2"),
    ]
    summary = summarize_coordinates(
        observations,
        19.1947,
        72.9737,
        radius_m=200,
        start=start,
        end=end,
    )
    assert summary.generated_mass_kg_low == 140
    assert summary.generated_mass_kg_high == 170
    assert summary.removed_mass_kg_low == 100
    assert summary.removed_mass_kg_high == 120
    assert summary.current_mass_kg_low == 40
    assert summary.current_mass_kg_high == 50


def test_no_coverage_is_not_reported_as_zero_waste():
    end = datetime(2026, 9, 11, 16, 0, tzinfo=UTC)
    summary = summarize_coordinates([], 19.1947, 72.9737, end=end)
    assert summary.observations == 0
    assert summary.generated_mass_kg_low is None
    assert "not proof of zero waste" in summary.caveat
