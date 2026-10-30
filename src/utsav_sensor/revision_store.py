from __future__ import annotations

import asyncio
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from .history import ObservationRevision, build_hotspots_from_revisions_as_of, replay_observation_revisions
from .models import HotspotState, Observation


class SQLiteRevisionLedger:
    """Opt-in local append-only revision ledger, separate from the live upsert store.

    SQLite triggers prevent accidental SQL UPDATE/DELETE; database owners can
    still rewrite the file or drop triggers. This is not an authenticated audit
    service, and it does not backfill history that was previously overwritten.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    async def start(self) -> None:
        await asyncio.to_thread(self._start_sync)

    def _start_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS observation_revisions (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    recorded_at TEXT NOT NULL,
                    observation_id TEXT NOT NULL,
                    payload TEXT
                )
            """)
            db.execute("""
                CREATE TRIGGER IF NOT EXISTS revision_no_update
                BEFORE UPDATE ON observation_revisions
                BEGIN SELECT RAISE(ABORT, 'revision ledger is append-only'); END
            """)
            db.execute("""
                CREATE TRIGGER IF NOT EXISTS revision_no_delete
                BEFORE DELETE ON observation_revisions
                BEGIN SELECT RAISE(ABORT, 'revision ledger is append-only'); END
            """)

    async def append(
        self, observation: Observation | None, *, observation_id: str | None = None
    ) -> ObservationRevision:
        """Issue a sequence and UTC receipt in one SQLite write transaction.

        Pass None with observation_id to record a deletion tombstone. The caller
        does not control receipt time or sequence. No live upsert is performed.
        """
        if observation is None:
            if not observation_id:
                raise ValueError("tombstones require observation_id")
            snapshot = None
            record_id = observation_id
        else:
            snapshot = Observation.model_validate(observation.model_dump())
            record_id = observation_id or snapshot.id
            if record_id != snapshot.id or not record_id:
                raise ValueError("revision ID does not match observation")
            if (
                snapshot.observed_at.tzinfo is None
                or snapshot.observed_at.utcoffset() is None
                or snapshot.ingested_at.tzinfo is None
                or snapshot.ingested_at.utcoffset() is None
            ):
                raise ValueError("observation timestamps must be timezone-aware")
        return await asyncio.to_thread(self._append_sync, record_id, snapshot)

    def _append_sync(self, record_id: str, snapshot: Observation | None) -> ObservationRevision:
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            last = db.execute(
                "SELECT recorded_at FROM observation_revisions ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            now = datetime.now(UTC)
            if last is not None and now < datetime.fromisoformat(last[0]):
                raise ValueError("server clock moved backwards relative to last receipt")
            if snapshot is not None and snapshot.ingested_at > now:
                raise ValueError("observation ingestion cannot postdate revision receipt")
            cursor = db.execute(
                "INSERT INTO observation_revisions(recorded_at, observation_id, payload) "
                "VALUES (?, ?, ?)",
                (now.isoformat(), record_id, None if snapshot is None else snapshot.model_dump_json()),
            )
            sequence = cursor.lastrowid
        return ObservationRevision(sequence, now, record_id, snapshot)

    async def revisions(
        self, *, expected_head_sequence: int | None = None
    ) -> list[ObservationRevision]:
        """Read complete ledger, optionally requiring an external trusted head.

        Without a trusted external checkpoint, a deleted final suffix cannot
        be detected. This parameter is a comparison, not signature validation.
        """
        return await asyncio.to_thread(self._revisions_sync, expected_head_sequence)

    def _revisions_sync(self, expected_head_sequence: int | None) -> list[ObservationRevision]:
        if expected_head_sequence is not None and (
            type(expected_head_sequence) is not int or expected_head_sequence < 0
        ):
            raise ValueError("expected_head_sequence must be a nonnegative integer")
        with closing(sqlite3.connect(self.path)) as db:
            rows = db.execute(
                "SELECT sequence, recorded_at, observation_id, payload "
                "FROM observation_revisions ORDER BY sequence"
            ).fetchall()
        revisions = [
            ObservationRevision(
                sequence,
                datetime.fromisoformat(recorded_at),
                observation_id,
                None if payload is None else Observation.model_validate_json(payload),
            )
            for sequence, recorded_at, observation_id, payload in rows
        ]
        # Validate the entire log, not only events before a requested cutoff.
        replay_observation_revisions(revisions, datetime.max.replace(tzinfo=UTC))
        if expected_head_sequence is not None and len(revisions) != expected_head_sequence:
            raise ValueError("revision log does not match trusted head checkpoint")
        return revisions

    async def hotspots_as_of(
        self, as_of: datetime, *, expected_head_sequence: int | None = None
    ) -> list[HotspotState]:
        revisions = await self.revisions(expected_head_sequence=expected_head_sequence)
        return build_hotspots_from_revisions_as_of(revisions, as_of)
