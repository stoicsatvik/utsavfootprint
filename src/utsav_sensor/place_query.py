from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import lru_cache

import httpx
from pydantic import BaseModel, Field

from .fusion import build_hotspots, cluster_observations, haversine_m
from .models import Observation, Provenance


class GeocodedPlace(BaseModel):
    query: str
    display_name: str
    lat: float
    lon: float
    provider: str = "openstreetmap_nominatim"


class PlaceWasteSummary(BaseModel):
    place: GeocodedPlace | None = None
    center_lat: float
    center_lon: float
    radius_m: float
    start: datetime
    end: datetime
    observations: int
    independent_sources: int
    hotspot_count: int
    current_mass_kg_low: float | None = None
    current_mass_kg_high: float | None = None
    generated_mass_kg_low: float | None = None
    generated_mass_kg_high: float | None = None
    removed_mass_kg_low: float | None = None
    removed_mass_kg_high: float | None = None
    unresolved_waste_hours_low: float | None = None
    unresolved_waste_hours_high: float | None = None
    confidence: float = Field(ge=0, le=1)
    mass_basis_counts: dict[str, int]
    caveat: str


@lru_cache(maxsize=256)
def _cached_geocode_key(query: str) -> str:
    return query.strip().lower()


async def geocode_place(query: str, timeout_seconds: float = 8.0) -> GeocodedPlace:
    """Geocode a human place name using Nominatim.

    This is discovery, not a truth source for waste. The result only defines the
    spatial query center. Operators can bypass it and query by coordinates.
    """
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("place query cannot be empty")

    _cached_geocode_key(cleaned)
    headers = {"User-Agent": "UtsavFootprint/0.3 (+https://github.com/stoicsatvik/utsavfootprint)"}
    params = {"q": cleaned, "format": "jsonv2", "limit": 1}
    async with httpx.AsyncClient(timeout=timeout_seconds, headers=headers) as client:
        response = await client.get("https://nominatim.openstreetmap.org/search", params=params)
        response.raise_for_status()
    rows = response.json()
    if not rows:
        raise LookupError(f"place not found: {cleaned}")
    row = rows[0]
    return GeocodedPlace(
        query=cleaned,
        display_name=row.get("display_name", cleaned),
        lat=float(row["lat"]),
        lon=float(row["lon"]),
    )


def _mass_pair(obs: Observation) -> tuple[float, float] | None:
    if obs.mass_kg_low is None or obs.mass_kg_high is None:
        return None
    return float(obs.mass_kg_low), float(obs.mass_kg_high)


def _track_ledger(track: list[Observation]) -> tuple[float, float, float, float, float, float]:
    """Estimate generated, removed and current mass for one spatial track.

    The ledger is deliberately conservative. Repeated views do not get summed.
    New generation is counted only when the estimated mass interval rises beyond
    the previous interval, or when a new open observation follows a cleaned state.
    """
    generated_low = generated_high = 0.0
    removed_low = removed_high = 0.0
    current_low = current_high = 0.0
    prev_low = prev_high = 0.0
    had_mass = False
    cleaned = True

    rank = {
        Provenance.VERIFIED_OFFICIAL: 4,
        Provenance.MEASURED: 4,
        Provenance.OBSERVED: 2,
        Provenance.MODELLED: 1,
    }

    # Collapse near-simultaneous observations into 20-minute buckets and keep the
    # strongest provenance record in each bucket. That cuts duplicate-photo noise.
    buckets: dict[int, Observation] = {}
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    for obs in sorted(track, key=lambda o: o.observed_at):
        bucket = int((obs.observed_at - epoch).total_seconds() // 1200)
        current = buckets.get(bucket)
        if current is None or rank[obs.provenance] > rank[current.provenance] or (
            rank[obs.provenance] == rank[current.provenance] and obs.confidence > current.confidence
        ):
            buckets[bucket] = obs

    for obs in sorted(buckets.values(), key=lambda o: o.observed_at):
        if obs.status in {"cleaned", "verified"}:
            if not cleaned and had_mass:
                removed_low += prev_low
                removed_high += prev_high
            current_low = current_high = 0.0
            prev_low = prev_high = 0.0
            had_mass = False
            cleaned = True
            continue

        pair = _mass_pair(obs)
        if pair is None:
            continue
        low, high = pair

        if cleaned or not had_mass:
            generated_low += low
            generated_high += high
        else:
            # Only count interval growth that cannot be explained by the previous
            # uncertainty range. This intentionally under-counts rather than lies.
            generated_low += max(0.0, low - prev_high)
            generated_high += max(0.0, high - prev_low)

        prev_low, prev_high = low, high
        current_low, current_high = low, high
        had_mass = True
        cleaned = False

    return generated_low, generated_high, removed_low, removed_high, current_low, current_high


def summarize_coordinates(
    observations: list[Observation],
    lat: float,
    lon: float,
    *,
    radius_m: float = 500.0,
    start: datetime | None = None,
    end: datetime | None = None,
    place: GeocodedPlace | None = None,
) -> PlaceWasteSummary:
    end = end or datetime.now(UTC)
    start = start or end - timedelta(hours=24)
    if start > end:
        raise ValueError("start must not be after end")
    if radius_m <= 0:
        raise ValueError("radius_m must be positive")

    scoped = [
        o
        for o in observations
        if start <= o.observed_at <= end and haversine_m(lat, lon, o.lat, o.lon) <= radius_m
    ]

    if not scoped:
        return PlaceWasteSummary(
            place=place,
            center_lat=lat,
            center_lon=lon,
            radius_m=radius_m,
            start=start,
            end=end,
            observations=0,
            independent_sources=0,
            hotspot_count=0,
            confidence=0.0,
            mass_basis_counts={},
            caveat="No observations exist in this place/time window; zero observations is not proof of zero waste.",
        )

    # Spatial tracks persist across the whole query window. A smaller radius than
    # hotspot presentation clustering reduces accidental merging of nearby piles.
    tracks = cluster_observations(scoped, radius_m=60.0, window_hours=max(24.0, (end - start).total_seconds() / 3600 + 1))

    gen_low = gen_high = rem_low = rem_high = cur_low = cur_high = 0.0
    have_any_mass = False
    for track in tracks:
        values = _track_ledger(track)
        if any(_mass_pair(o) is not None for o in track):
            have_any_mass = True
            gl, gh, rl, rh, cl, ch = values
            gen_low += gl
            gen_high += gh
            rem_low += rl
            rem_high += rh
            cur_low += cl
            cur_high += ch

    hotspots = build_hotspots(scoped, now=end)
    uwh_low = sum(h.unresolved_waste_hours_low or 0.0 for h in hotspots)
    uwh_high = sum(h.unresolved_waste_hours_high or 0.0 for h in hotspots)

    # Independent source confidence. Repeated observations by one camera/person do
    # not multiply confidence indefinitely.
    by_source: dict[str, float] = {}
    for o in scoped:
        by_source[o.source_id] = max(by_source.get(o.source_id, 0.0), o.confidence)
    confidence = 1.0
    for strength in by_source.values():
        confidence *= 1.0 - min(max(strength, 0.0), 0.95)
    confidence = 1.0 - confidence

    basis_counts: dict[str, int] = {}
    for o in scoped:
        if _mass_pair(o) is not None:
            basis_counts[o.provenance.value] = basis_counts.get(o.provenance.value, 0) + 1

    return PlaceWasteSummary(
        place=place,
        center_lat=lat,
        center_lon=lon,
        radius_m=radius_m,
        start=start,
        end=end,
        observations=len(scoped),
        independent_sources=len(by_source),
        hotspot_count=len(hotspots),
        current_mass_kg_low=cur_low if have_any_mass else None,
        current_mass_kg_high=cur_high if have_any_mass else None,
        generated_mass_kg_low=gen_low if have_any_mass else None,
        generated_mass_kg_high=gen_high if have_any_mass else None,
        removed_mass_kg_low=rem_low if have_any_mass else None,
        removed_mass_kg_high=rem_high if have_any_mass else None,
        unresolved_waste_hours_low=uwh_low if have_any_mass else None,
        unresolved_waste_hours_high=uwh_high if have_any_mass else None,
        confidence=confidence,
        mass_basis_counts=basis_counts,
        caveat=(
            "Generated mass is an evidence-led interval derived from observed state changes. "
            "It is not a physical measurement unless the underlying provenance says measured/verified_official."
        ),
    )
