from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
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
            # SQLite's INSERT OR REPLACE can implicitly delete an existing
            # primary-key row without firing DELETE triggers when
            # PRAGMA recursive_triggers is off (SQLite's default).
            # Guard collisions at BEFORE INSERT, before REPLACE can erase a row.
            # This protects against ordinary accidental REPLACE statements,
            # not a privileged owner who can modify triggers or the database.
            db.execute("""
                CREATE TRIGGER IF NOT EXISTS revision_no_replace
                BEFORE INSERT ON observation_revisions
                WHEN EXISTS (
                    SELECT 1 FROM observation_revisions
                    WHERE sequence = NEW.sequence
                )
                BEGIN SELECT RAISE(ABORT, 'revision sequence already exists'); END
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

    async def checkpoint(self) -> tuple[int, str]:
        """Compute a read-only SHA-256 receipt over the complete raw SQLite log.

        The returned (head_sequence, digest) becomes useful evidence only if a
        trusted party retains it OUTSIDE this database. It is not signed,
        timestamped by an independent authority, or automatically exported.
        """
        return await asyncio.to_thread(self._checkpoint_sync)

    def _checkpoint_sync(self) -> tuple[int, str]:
        # Domain separation and length framing make this digest format
        # unambiguous; version the prefix if its serialization ever changes.
        digest = hashlib.sha256(b"utsav-revision-ledger-checkpoint-v1\x00")
        head = 0
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("BEGIN")  # One consistent SQLite read snapshot.
            rows = db.execute(
                "SELECT sequence, recorded_at, observation_id, payload "
                "FROM observation_revisions ORDER BY sequence"
            )
            for row in rows:
                if type(row[0]) is not int or row[0] != head + 1:
                    raise ValueError("revision sequence gap or missing prefix")
                encoded = json.dumps(
                    row, ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8")
                digest.update(len(encoded).to_bytes(8, "big"))
                digest.update(encoded)
                head += 1
        return head, digest.hexdigest()

    async def verify_checkpoint(
        self, expected_head_sequence: int, expected_sha256: str
    ) -> None:
        """Fail closed if current ledger differs from an externally saved receipt.

        A locally generated or database-co-located expected value is NOT a
        trusted checkpoint; an attacker able to rewrite both can evade this.
        """
        if (
            type(expected_head_sequence) is not int
            or expected_head_sequence < 0
            or not isinstance(expected_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
        ):
            raise ValueError("invalid external revision checkpoint")
        actual_head, actual_sha256 = await self.checkpoint()
        if (
            actual_head != expected_head_sequence
            or not hmac.compare_digest(actual_sha256, expected_sha256)
        ):
            raise ValueError("revision checkpoint mismatch")

    async def hotspots_as_of(
        self, as_of: datetime, *, expected_head_sequence: int | None = None
    ) -> list[HotspotState]:
        revisions = await self.revisions(expected_head_sequence=expected_head_sequence)
        return build_hotspots_from_revisions_as_of(revisions, as_of)
