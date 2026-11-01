"""Opt-in, evidence-weighted location for a reopened hotspot's *current* episode.

This helper intentionally does not alter HotspotState.lat/lon, which continue
representing historical cluster identity. Declared cleanup provenance is not
authenticated; no physical pile-identity or field-location accuracy is claimed.
"""
from __future__ import annotations

from datetime import UTC, datetime

from .fusion import (
    FUTURE_CLOCK_SKEW_SECONDS,
    _representatives_by_source,
    _spherical_centroid,
    observation_strength,
)
from .models import Observation, Provenance


def reopened_episode_location(
    cluster: list[Observation], now: datetime | None = None
) -> tuple[float, float] | None:
    """Locate only positive-strength, strictly post-cleanup open observations.

    Return None when there is no declared credible cleanup, no reopening, an
    equal-time boundary without later evidence, or no positive current-episode
    positional evidence. Repeated reports from one source count once. This is
    a diagnostic candidate coordinate, not an authenticated physical location.
    """
    if not cluster:
        raise ValueError("cannot locate empty cluster")
    now = now or datetime.now(UTC)
    if any(
        (obs.observed_at - now).total_seconds() > FUTURE_CLOCK_SKEW_SECONDS
        for obs in cluster
    ):
        raise ValueError("future-dated observation exceeds clock-skew tolerance")

    terminal = {"cleaned", "verified"}
    credible = {Provenance.MEASURED, Provenance.VERIFIED_OFFICIAL}
    last_closure = max(
        (
            obs.observed_at
            for obs in cluster
            if obs.status in terminal and obs.provenance in credible
        ),
        default=None,
    )
    if last_closure is None:
        return None
    if not any(
        obs.status not in terminal and obs.observed_at >= last_closure
        for obs in cluster
    ):
        return None

    # Strictly later open evidence only; closure-time ties cannot be assigned
    # to the new pile. Do not use closed/status-only terminal reports as anchors.
    current = [
        obs for obs in cluster
        if obs.status not in terminal and obs.observed_at > last_closure
    ]
    representatives = _representatives_by_source(current, now)
    positive = [
        (obs, strength)
        for obs in representatives
        if (strength := observation_strength(obs, now)) > 0
    ]
    if not positive:
        return None
    return _spherical_centroid(
        [obs for obs, _ in positive], [strength for _, strength in positive]
    )
