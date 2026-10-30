from __future__ import annotations

import math
from collections import defaultdict
from datetime import UTC, datetime

from .models import HotspotState, Observation, Provenance

FUTURE_CLOCK_SKEW_SECONDS = 300.0  # Explicit tolerance for minor sensor clock skew.

PROVENANCE_WEIGHT = {
    Provenance.VERIFIED_OFFICIAL: 1.00,
    Provenance.MEASURED: 0.98,
    Provenance.OBSERVED: 0.80,
    Provenance.MODELLED: 0.35,
}


def haversine_m(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = math.radians(b_lat - a_lat)
    dl = math.radians(b_lon - a_lon)
    q = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(q))


def freshness(observed_at: datetime, now: datetime, half_life_hours: float = 4.0) -> float:
    age_h = max(0.0, (now - observed_at).total_seconds() / 3600)
    return 0.5 ** (age_h / half_life_hours)


def observation_strength(obs: Observation, now: datetime) -> float:
    return max(
        0.0,
        min(
            1.0,
            PROVENANCE_WEIGHT[obs.provenance]
            * obs.confidence
            * obs.media_quality
            * freshness(obs.observed_at, now),
        ),
    )


def _spherical_centroid(
    observations: list[Observation], weights: list[float] | None = None
) -> tuple[float, float]:
    """Weighted unit-sphere centroid; handles dateline and high-latitude geometry.

    For an undefined antipodal resultant, retain a real source location
    selected by stable ID, not by ingestion/list order.
    """
    if not observations:
        raise ValueError("cannot locate empty observations")
    if weights is None:
        weights = [1.0] * len(observations)
    if len(weights) != len(observations) or any(
        not math.isfinite(w) or w < 0 for w in weights
    ):
        raise ValueError("invalid positional weights")
    x = y = z = 0.0
    for obs, weight in zip(observations, weights, strict=True):
        latitude, longitude = math.radians(obs.lat), math.radians(obs.lon)
        x += weight * math.cos(latitude) * math.cos(longitude)
        y += weight * math.cos(latitude) * math.sin(longitude)
        z += weight * math.sin(latitude)
    anchor = min(observations, key=lambda obs: obs.id)
    if math.sqrt(x * x + y * y + z * z) < 1e-12:
        return anchor.lat, anchor.lon
    horizontal = math.hypot(x, y)
    latitude = math.degrees(math.atan2(z, horizontal))
    longitude = (math.degrees(math.atan2(y, x))
                 if horizontal >= 1e-12 else anchor.lon)
    return latitude, longitude


def cluster_observations(
    observations: list[Observation], radius_m: float = 120.0, window_hours: float = 24.0
) -> list[list[Observation]]:
    """Greedy clustering with pairwise spatial and full temporal-span bounds.

    A centroid-only radius can absorb observations more than radius_m apart.
    A newest-only time check can similarly chain reports over many windows.
    These guards prevent both. Canonical time/physical-coordinate ordering
    avoids arbitrary ID-based partitions for distinct positions; it is still
    a greedy heuristic, not physical pile identity or perturbation stability.
    """
    clusters: list[list[Observation]] = []
    if not observations:
        return clusters

    # Place the longitude seam in the largest unoccupied circular gap so
    # neighbouring reports across the antimeridian retain spatial order.
    longitudes = sorted({o.lon % 360.0 for o in observations})
    if len(longitudes) == 1:
        longitude_origin = longitudes[0]
    else:
        seam = max(
            range(len(longitudes)),
            key=lambda i: (
                (longitudes[(i + 1) % len(longitudes)] - longitudes[i]) % 360.0,
                -i,
            ),
        )
        longitude_origin = longitudes[(seam + 1) % len(longitudes)]

    for obs in sorted(
        observations,
        key=lambda o: (
            o.observed_at,
            o.lat,
            (o.lon % 360.0 - longitude_origin) % 360.0,
            o.id,  # only breaks ties between physically coincident observations
        ),
    ):
        best: list[Observation] | None = None
        best_d = float("inf")
        for c in clusters:
            oldest = min(o.observed_at for o in c)
            newest = max(o.observed_at for o in c)
            if (
                max(obs.observed_at, newest) - min(obs.observed_at, oldest)
            ).total_seconds() > window_hours * 3600:
                continue
            if any(
                haversine_m(obs.lat, obs.lon, other.lat, other.lon) > radius_m
                for other in c
            ):
                continue
            c_lat, c_lon = _spherical_centroid(c)
            d = haversine_m(obs.lat, obs.lon, c_lat, c_lon)
            if d <= radius_m and d < best_d:
                best, best_d = c, d
        if best is None:
            clusters.append([obs])
        else:
            best.append(obs)
    return clusters



def _representatives_by_source(
    observations: list[Observation], now: datetime
) -> list[Observation]:
    """Use one strongest report per source in evidence-weighted fusion.

    A replay of identical evidence must not acquire extra voting power.
    Stronger or fresher reports from the same source can replace earlier ones;
    this is not an identity-resolution or sensor-independence guarantee.
    """
    selected: dict[str, Observation] = {}
    for obs in observations:
        previous = selected.get(obs.source_id)
        if previous is None or (
            observation_strength(obs, now), obs.observed_at, obs.id
        ) > (
            observation_strength(previous, now), previous.observed_at, previous.id
        ):
            selected[obs.source_id] = obs
    return list(selected.values())


def _finite_nonnegative_median(values: list[float]) -> float:
    """Compute an even-sample median without overflowing finite positive inputs."""
    if not values or any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("mass samples must be finite and nonnegative")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    lower, upper = ordered[middle - 1], ordered[middle]
    return lower + (upper - lower) / 2


def _finite_waste_hours(mass: float | None, hours: float) -> tuple[float | None, bool]:
    """Return a finite metric or a flagged overflow, retaining original mass evidence."""
    if mass is None:
        return None, False
    result = mass * hours
    if not math.isfinite(result):
        return None, True
    return result, False


def _fuse_mass(cluster: list[Observation], now: datetime):
    candidates = [o for o in cluster if o.mass_kg_low is not None and o.mass_kg_high is not None]
    if not candidates:
        return None, None, None

    # Repeated views estimate one latent pile; they are never summed.
    rank = {
        Provenance.VERIFIED_OFFICIAL: 3,
        Provenance.MEASURED: 3,
        Provenance.OBSERVED: 2,
        Provenance.MODELLED: 1,
    }
    best_rank = max(rank[o.provenance] for o in candidates)
    candidates = [o for o in candidates if rank[o.provenance] == best_rank]
    candidates = _representatives_by_source(candidates, now)

    weighted = []
    for o in candidates:
        s = max(observation_strength(o, now), 0.01)
        weighted.append((o.mass_kg_low, o.mass_kg_high, s, o.provenance))

    low = _finite_nonnegative_median([x[0] for x in weighted])
    high = _finite_nonnegative_median([x[1] for x in weighted])
    basis = max((x[3] for x in weighted), key=lambda p: PROVENANCE_WEIGHT[p])
    return low, high, basis


def _resolution_episode(
    cluster: list[Observation], now: datetime
) -> tuple[str, float]:
    """Resolve status and duration from chronological, declared-provenance events.

    An older open report cannot keep a subsequently *declared measured/official*
    cleanup unresolved forever. A later open report starts a new episode.
    A citizen's unverified cleanup assertion alone cannot close a hotspot.
    Same-time open and closure remain unresolved conservatively.

    Provenance labels are NOT authenticated here: ingestion authorization and
    physical cleanup verification remain independent system requirements.
    """
    terminal = {"cleaned", "verified"}
    closure_provenance = {Provenance.MEASURED, Provenance.VERIFIED_OFFICIAL}
    closures = [
        o for o in cluster
        if o.status in terminal and o.provenance in closure_provenance
    ]
    last_closure_time = max((o.observed_at for o in closures), default=None)
    pending = [
        o for o in cluster
        if o.status not in terminal
        and (last_closure_time is None or o.observed_at >= last_closure_time)
    ]
    if pending:
        latest = max(pending, key=lambda o: (o.observed_at, o.id))
        since = min(o.observed_at for o in pending)
        return latest.status, max(0.0, (now - since).total_seconds() / 3600)
    if closures:
        latest = max(closures, key=lambda o: (o.observed_at, o.id))
        return latest.status, 0.0
    # No declared credible closure, including the all-unverified-closed case.
    since = min(o.observed_at for o in cluster)
    return "open", max(0.0, (now - since).total_seconds() / 3600)


def fuse_cluster(cluster: list[Observation], now: datetime | None = None) -> HotspotState:
    if not cluster:
        raise ValueError("cannot fuse empty cluster")
    now = now or datetime.now(UTC)
    # Direct fusion must not let a future event rewrite an as-of snapshot.
    # Ingest may retain such records for later evaluation; the current view
    # rejects timestamps beyond the explicit five-minute skew tolerance.
    if any((o.observed_at - now).total_seconds() > FUTURE_CLOCK_SKEW_SECONDS for o in cluster):
        raise ValueError("future-dated observation exceeds clock-skew tolerance")

    strengths = [observation_strength(o, now) for o in cluster]
    representatives = _representatives_by_source(cluster, now)
    representative_strengths = [observation_strength(o, now) for o in representatives]
    # A zero-confidence observation still has a location; zero evidence must not
    # move the hotspot to (0, 0). Confidence itself remains zero.
    # Repeated reports from one source cannot multiply its position weight.
    position_weights = (
        representative_strengths
        if sum(representative_strengths) > 0
        else [1.0] * len(representatives)
    )
    lat, lon = _spherical_centroid(representatives, position_weights)

    strongest_by_source: dict[str, float] = {}
    for o, s in zip(cluster, strengths, strict=True):
        strongest_by_source[o.source_id] = max(strongest_by_source.get(o.source_id, 0.0), s)
    combined_confidence = 1.0
    for s in strongest_by_source.values():
        combined_confidence *= 1.0 - min(s, 0.995)
    combined_confidence = 1.0 - combined_confidence

    last_seen = max(o.observed_at for o in cluster)
    fresh = freshness(last_seen, now)

    material_num: dict[str, float] = defaultdict(float)
    material_den: dict[str, float] = defaultdict(float)
    for o, s in zip(representatives, representative_strengths, strict=True):
        for k, p in o.materials.items():
            material_num[k] += p * s
            material_den[k] += s
    materials = {
        k: round(material_num[k] / material_den[k], 4)
        for k in material_num
        if material_den[k] > 0
    }

    low, high, basis = _fuse_mass(cluster, now)
    effective_status, unresolved_hours = _resolution_episode(cluster, now)
    waste_low, overflow_low = _finite_waste_hours(low, unresolved_hours)
    waste_high, overflow_high = _finite_waste_hours(high, unresolved_hours)
    hotspot_id = "hs_" + min(o.id for o in cluster).replace("-", "")[:16]
    return HotspotState(
        id=hotspot_id,
        lat=lat,
        lon=lon,
        status=effective_status,
        observation_count=len(cluster),
        independent_sources=len(strongest_by_source),
        last_observed_at=last_seen,
        freshness=fresh,
        confidence=combined_confidence,
        materials=materials,
        mass_kg_low=low,
        mass_kg_high=high,
        mass_basis=basis,
        unresolved_hours=unresolved_hours,
        unresolved_waste_hours_low=waste_low,
        unresolved_waste_hours_high=waste_high,
        unresolved_waste_hours_overflow=overflow_low or overflow_high,
        unresolved_waste_hours_overflow_low=overflow_low,
        unresolved_waste_hours_overflow_high=overflow_high,
        observation_ids=[o.id for o in cluster],
    )


def build_hotspots(observations: list[Observation], now: datetime | None = None) -> list[HotspotState]:
    now = now or datetime.now(UTC)
    # Future events outside tolerated clock skew are not current evidence.
    # Do not mutate the observation store: they can become eligible later.
    active = [
        o for o in observations
        if -FUTURE_CLOCK_SKEW_SECONDS <= (now - o.observed_at).total_seconds() <= 72 * 3600
    ]
    return [fuse_cluster(c, now) for c in cluster_observations(active)]


def build_hotspots_as_of(
    observations: list[Observation], as_of: datetime
) -> list[HotspotState]:
    """Reconstruct a strict historical snapshot from append-only observations.

    A record is eligible only after *both* its event time and ingestion time.
    Unlike the live `build_hotspots` view, no future clock-skew allowance is
    applied. This prevents hindsight leakage from backfilled observations.

    This is an opt-in research/history helper: it assumes immutable, complete
    observation records. It does not reconstruct historical edits/deletions,
    authenticate provenance, or alter the live clock-skew policy.
    """
    eligible = [
        o for o in observations
        if o.observed_at <= as_of and o.ingested_at <= as_of
    ]
    return build_hotspots(eligible, now=as_of)
