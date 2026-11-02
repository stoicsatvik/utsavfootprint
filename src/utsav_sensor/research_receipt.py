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


class ResearchReceiptIntegrityError(ValueError):
    """Stored receipt and canonical evidence disagree; do not trust either."""


def _verified_receipt(row: tuple[str, str, str], expected_id: str) -> Observation:
    """Fail closed on inconsistent SQLite row fields (not a MAC or signature)."""
    stored_evidence, payload, stored_receipt_at = row
    try:
        item = Observation.model_validate_json(payload)
        if (
            item.id != expected_id
            or _evidence_key(item) != stored_evidence
            or item.ingested_at.isoformat() != stored_receipt_at
        ):
            raise ResearchReceiptIntegrityError("stored receipt/evidence mismatch")
    except (ValueError, TypeError) as exc:
        if isinstance(exc, ResearchReceiptIntegrityError):
            raise
        raise ResearchReceiptIntegrityError("invalid stored receipt payload") from exc
    return item


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
                    payload TEXT NOT NULL,
                    receipt_at TEXT NOT NULL
                )"""
            )
            db.commit()
            # Fail closed on old research databases. Backfilling a receipt from
            # its mutable payload would falsely claim an independent time witness.
            columns = {row[1] for row in db.execute("PRAGMA table_info(research_first_receipts)")}
            if "receipt_at" not in columns:
                raise ResearchReceiptIntegrityError(
                    "legacy research receipt schema lacks receipt_at; no automatic migration"
                )

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
                    "SELECT evidence, payload, receipt_at FROM research_first_receipts WHERE id = ?",
                    (observation.id,),
                ).fetchone()
                if row is not None:
                    result = _verified_receipt(row, observation.id)
                    if row[0] != evidence:
                        raise ObservationConflictError(
                            "observation ID already exists with different evidence"
                        )
                else:
                    receipt = self.clock()
                    if receipt.tzinfo is None or receipt.utcoffset() is None:
                        raise ValueError("receipt clock must return an aware datetime")
                    result = observation.model_copy(
                        update={"ingested_at": receipt.astimezone(UTC)}
                    )
                    db.execute(
                        "INSERT INTO research_first_receipts(id, evidence, payload, receipt_at) "
                        "VALUES (?, ?, ?, ?)",
                        (
                            observation.id,
                            evidence,
                            result.model_dump_json(),
                            result.ingested_at.isoformat(),
                        ),
                    )
                db.execute("COMMIT")
                return result
            except BaseException:
                # SQLITE_FULL can auto-rollback a transaction. A second SQL
                # ROLLBACK would then mask the original storage failure with
                # "cannot rollback - no transaction is active".
                if db.in_transaction:
                    try:
                        db.rollback()
                    except sqlite3.Error:
                        # Closing the connection is the final cleanup boundary;
                        # preserve the triggering error for diagnosis.
                        pass
                raise

    def get(self, observation_id: str) -> Observation | None:
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            row = db.execute(
                "SELECT evidence, payload, receipt_at FROM research_first_receipts WHERE id = ?",
                (observation_id,),
            ).fetchone()
        return _verified_receipt(row, observation_id) if row else None
