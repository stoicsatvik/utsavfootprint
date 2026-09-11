from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median

from .models import HotspotState, Observation, Provenance

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


def cluster_observations(
    observations: list[Observation], radius_m: float = 120.0, window_hours: float = 24.0
) -> list[list[Observation]]:
    """Greedy spatiotemporal clustering. Deterministic for timestamp-sorted input.

    The radius is intentionally tight enough for street-scale reports. Production can replace this
    with H3/DBSCAN without changing the fusion contract.
    """
    clusters: list[list[Observation]] = []
    for obs in sorted(observations, key=lambda x: (x.observed_at, x.id)):
        best: list[Observation] | None = None
        best_d = float("inf")
        for c in clusters:
            newest = max(o.observed_at for o in c)
            if abs((obs.observed_at - newest).total_seconds()) > window_hours * 3600:
                continue
            c_lat = sum(o.lat for o in c) / len(c)
            c_lon = sum(o.lon for o in c) / len(c)
            d = haversine_m(obs.lat, obs.lon, c_lat, c_lon)
            if d <= radius_m and d < best_d:
                best, best_d = c, d
        if best is None:
            clusters.append([obs])
        else:
            best.append(obs)
    return clusters


def _fuse_mass(cluster: list[Observation], now: datetime):
    candidates = [o for o in cluster if o.mass_kg_low is not None and o.mass_kg_high is not None]
    if not candidates:
        return None, None, None

    # A measured/official value dominates model/citizen estimates. Repeated views of the same pile
    # are estimates of one latent mass, so they are NEVER summed.
    rank = {
        Provenance.VERIFIED_OFFICIAL: 3,
        Provenance.MEASURED: 3,
        Provenance.OBSERVED: 2,
        Provenance.MODELLED: 1,
    }
    best_rank = max(rank[o.provenance] for o in candidates)
    candidates = [o for o in candidates if rank[o.provenance] == best_rank]

    weighted = []
    for o in candidates:
        s = max(observation_strength(o, now), 0.01)
        weighted.append((o.mass_kg_low, o.mass_kg_high, s, o.provenance))

    # Robust against one wild estimate: use medians, while retaining uncertainty bounds.
    low = float(median([x[0] for x in weighted]))
    high = float(median([x[1] for x in weighted]))
    basis = max((x[3] for x in weighted), key=lambda p: PROVENANCE_WEIGHT[p])
    return low, high, basis


def fuse_cluster(cluster: list[Observation], now: datetime | None = None) -> HotspotState:
    if not cluster:
        raise ValueError("cannot fuse empty cluster")
    now = now or datetime.now(timezone.utc)

    strengths = [observation_strength(o, now) for o in cluster]
    total_s = sum(strengths) or 1.0
    lat = sum(o.lat * s for o, s in zip(cluster, strengths)) / total_s
    lon = sum(o.lon * s for o, s in zip(cluster, strengths)) / total_s

    # Independent corroboration increases confidence, but correlated reports from the same source
    # do not. No single weak report can become 'certain' merely by being replayed.
    strongest_by_source: dict[str, float] = {}
    for o, s in zip(cluster, strengths):
        strongest_by_source[o.source_id] = max(strongest_by_source.get(o.source_id, 0.0), s)
    combined_confidence = 1.0
    for s in strongest_by_source.values():
        combined_confidence *= 1.0 - min(s, 0.995)
    combined_confidence = 1.0 - combined_confidence

    last_seen = max(o.observed_at for o in cluster)
    fresh = freshness(last_seen, now)

    material_num: dict[str, float] = defaultdict(float)
    material_den: dict[str, float] = defaultdict(float)
    for o, s in zip(cluster, strengths):
        for k, p in o.materials.items():
            material_num[k] += p * s
            material_den[k] += s
    materials = {
        k: round(material_num[k] / material_den[k], 4)
        for k in material_num
        if material_den[k] > 0
    }

    low, high, basis = _fuse_mass(cluster, now)
    unresolved = any(o.status not in {"cleaned", "verified"} for o in cluster)
    first_open = min(o.observed_at for o in cluster)
    unresolved_hours = max(0.0, (now - first_open).total_seconds() / 3600) if unresolved else 0.0

    # Resolution evidence wins only when it is at least as recent as the latest open evidence.
    latest = max(cluster, key=lambda o: o.observed_at)
    status = latest.status

    hotspot_id = "hs_" + min(o.id for o in cluster).replace("-", "")[:16]
    return HotspotState(
        id=hotspot_id,
        lat=lat,
        lon=lon,
        status=status,
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
        unresolved_waste_hours_low=None if low is None else low * unresolved_hours,
        unresolved_waste_hours_high=None if high is None else high * unresolved_hours,
        observation_ids=[o.id for o in cluster],
    )


def build_hotspots(observations: list[Observation], now: datetime | None = None) -> list[HotspotState]:
    now = now or datetime.now(timezone.utc)
    active = [o for o in observations if (now - o.observed_at).total_seconds() <= 72 * 3600]
    return [fuse_cluster(c, now) for c in cluster_observations(active)]
