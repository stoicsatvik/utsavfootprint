from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .fusion import build_hotspots_as_of
from .models import HotspotState, Observation


@dataclass(frozen=True, slots=True)
class ObservationRevision:
    """One append-only, server-sequenced receipt; None is a deletion tombstone.

    recorded_at must be assigned by the trusted ingestion service. This
    in-memory helper does not authenticate or persist such receipts.
    """

    sequence: int
    recorded_at: datetime
    observation_id: str
    observation: Observation | None


def replay_observation_revisions(
    revisions: list[ObservationRevision], as_of: datetime
) -> list[Observation]:
    """Reconstruct known records at a cutoff, including edits and deletions.

    Sequence numbers must be unique, positive and chronological by receipt
    time. Equal receipt times are resolved by sequence. Fail closed on a
    malformed log instead of silently rewriting historical evidence.
    """
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    current: dict[str, Observation] = {}
    previous_recorded_at: datetime | None = None
    seen_sequences: set[int] = set()
    expected_sequence = 1

    for revision in sorted(revisions, key=lambda r: r.sequence):
        if type(revision.sequence) is not int or revision.sequence <= 0:
            raise ValueError("revision sequence must be a positive integer")
        if revision.sequence in seen_sequences:
            raise ValueError("duplicate revision sequence")
        seen_sequences.add(revision.sequence)
        if revision.sequence != expected_sequence:
            raise ValueError("incomplete revision log: sequence gap or missing prefix")
        expected_sequence += 1
        if not revision.observation_id:
            raise ValueError("empty revision observation_id")
        stamp = revision.recorded_at
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")
        if previous_recorded_at is not None and stamp < previous_recorded_at:
            raise ValueError("revision receipt timestamps are not chronological")
        previous_recorded_at = stamp
        obs = revision.observation
        if obs is not None:
            if obs.id != revision.observation_id:
                raise ValueError("revision ID does not match observation")
            if (
                obs.ingested_at.tzinfo is None
                or obs.ingested_at.utcoffset() is None
                or obs.observed_at.tzinfo is None
                or obs.observed_at.utcoffset() is None
            ):
                raise ValueError("observation timestamps must be timezone-aware")
            if obs.ingested_at > stamp:
                raise ValueError("observation ingestion cannot postdate revision receipt")
        if stamp > as_of:
            continue
        if obs is None:
            current.pop(revision.observation_id, None)
        else:
            current[revision.observation_id] = obs.model_copy(deep=True)

    return [current[key] for key in sorted(current)]


def build_hotspots_from_revisions_as_of(
    revisions: list[ObservationRevision], as_of: datetime
) -> list[HotspotState]:
    """Opt-in historical view from an externally retained revision log."""
    return build_hotspots_as_of(replay_observation_revisions(revisions, as_of), as_of)
