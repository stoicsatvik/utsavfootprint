"""Research-only SQLite first-receipt prototype; NOT wired into the public API.

A client-supplied ``ingested_at`` is not evidence of arrival time. This small
experiment separates immutable client evidence from a server-issued first
receipt and uses a SQLite write transaction to serialize competing writers.
It is not an authentication, anti-Sybil, or trusted-clock implementation.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from .errors import ObservationConflictError
from .models import Observation


def _evidence_key(observation: Observation) -> str:
    """Canonical client evidence; the untrusted receipt claim is excluded."""
    return json.dumps(
        observation.model_dump(mode="json", exclude={"ingested_at"}),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


class ResearchFirstReceiptStore:
    """Standalone experimental store, intentionally unused by production code."""

    def __init__(self, path: str | Path, *, clock: Callable[[], datetime] | None = None):
        self.path = Path(path)
        self.clock = clock or (lambda: datetime.now(UTC))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS research_first_receipts (
                    id TEXT PRIMARY KEY,
                    evidence TEXT NOT NULL,
                    payload TEXT NOT NULL
                )"""
            )
            db.commit()

    def put(self, observation: Observation) -> Observation:
        """First insert stamps server time; exact-evidence retries return it.

        BEGIN IMMEDIATE makes the ID check and insertion one SQLite transaction
        across independent connections. Conflicting IDs never overwrite rows.
        """
        evidence = _evidence_key(observation)
        with closing(sqlite3.connect(self.path, timeout=10, isolation_level=None)) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT evidence, payload FROM research_first_receipts WHERE id = ?",
                    (observation.id,),
                ).fetchone()
                if row is not None:
                    if row[0] != evidence:
                        raise ObservationConflictError(
                            "observation ID already exists with different evidence"
                        )
                    result = Observation.model_validate_json(row[1])
                else:
                    receipt = self.clock()
                    if receipt.tzinfo is None or receipt.utcoffset() is None:
                        raise ValueError("receipt clock must return an aware datetime")
                    result = observation.model_copy(
                        update={"ingested_at": receipt.astimezone(UTC)}
                    )
                    db.execute(
                        "INSERT INTO research_first_receipts(id, evidence, payload) "
                        "VALUES (?, ?, ?)",
                        (observation.id, evidence, result.model_dump_json()),
                    )
                db.execute("COMMIT")
                return result
            except BaseException:
                db.execute("ROLLBACK")
                raise

    def get(self, observation_id: str) -> Observation | None:
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            row = db.execute(
                "SELECT payload FROM research_first_receipts WHERE id = ?",
                (observation_id,),
            ).fetchone()
        return Observation.model_validate_json(row[0]) if row else None
