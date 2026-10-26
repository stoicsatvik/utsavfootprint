"""E296: compare server-owned CAS/idempotency with immutable event logging.

Disposable SQLite research only. Synthetic statuses do not authenticate cleanup.
No production SensorEngine or live database is changed.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

SCHEMA = """
# placeholder
""".replace("# placeholder", """
CREATE TABLE state (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, status TEXT NOT NULL);
CREATE TABLE mutations (key TEXT PRIMARY KEY, id TEXT NOT NULL, expected_revision INTEGER NOT NULL,
                        status TEXT NOT NULL, result_revision INTEGER NOT NULL);
CREATE TABLE events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
                     id TEXT NOT NULL, status TEXT NOT NULL);
""")


def initialize(db: sqlite3.Connection) -> None:
    db.executescript(SCHEMA)
    db.execute("INSERT INTO state(id, revision, status) VALUES ('shared', 1, 'open')")
    db.commit()


def cas_mutation(path: Path, *, key: str, expected: int, status: str) -> dict:
    """One durable revision claim and its retry receipt share an IMMEDIATE transaction."""
    with sqlite3.connect(path, timeout=5, isolation_level=None) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            old = db.execute(
                "SELECT id, expected_revision, status, result_revision FROM mutations WHERE key=?",
                (key,),
            ).fetchone()
            if old is not None:
                if old[:3] != ("shared", expected, status):
                    result = {"status": "IDEMPOTENCY_KEY_CONFLICT"}
                else:
                    result = {"status": "REPLAYED_COMMITTED", "revision": old[3]}
            else:
                changed = db.execute(
                    "UPDATE state SET revision=revision+1, status=? WHERE id='shared' AND revision=?",
                    (status, expected),
                ).rowcount
                if changed:
                    revision = expected + 1
                    db.execute(
                        "INSERT INTO mutations VALUES (?, ?, ?, ?, ?)",
                        (key, "shared", expected, status, revision),
                    )
                    result = {"status": "COMMITTED", "revision": revision}
                else:
                    result = {"status": "STALE_REVISION"}
            db.commit()
            return result
        except BaseException:
            db.rollback()
            raise


def append_event(path: Path, event_id: str, status: str) -> bool:
    with sqlite3.connect(path) as db:
        return bool(db.execute(
            "INSERT OR IGNORE INTO events(event_id,id,status) VALUES (?, 'shared', ?)",
            (event_id, status),
        ).rowcount)


def snapshot(path: Path) -> dict:
    with sqlite3.connect(path) as db:
        rev, status = db.execute("SELECT revision,status FROM state WHERE id='shared'").fetchone()
        events = db.execute("SELECT event_id,status FROM events ORDER BY sequence").fetchall()
    return {"revision": rev, "status": status, "events": events,
            "last_append_status": events[-1][1] if events else None}


def run(path: Path) -> dict:
    with sqlite3.connect(path) as db:
        initialize(db)
    current = cas_mutation(path, key="cleanup-1", expected=1, status="cleaned")
    stale = cas_mutation(path, key="old-open-1", expected=1, status="open")
    lost_ack_retry = cas_mutation(path, key="cleanup-1", expected=1, status="cleaned")
    mutated_retry = cas_mutation(path, key="cleanup-1", expected=1, status="open")
    for event_id, status in (("old-open", "open"), ("cleanup", "cleaned"),
                             ("late-open", "open")):
        append_event(path, event_id, status)
    duplicate_event_inserted = append_event(path, "cleanup", "cleaned")
    return {
        "schema": "utsav/e296/revision-vs-append-only/v1",
        "synthetic_only": True,
        "first_cas": current,
        "stale_cas": stale,
        "lost_ack_retry": lost_ack_retry,
        "idempotency_key_payload_conflict": mutated_retry,
        "duplicate_append_event_inserted": duplicate_event_inserted,
        "durable": snapshot(path),
        "inference": "CAS+idempotency rejects stale revisions and acknowledges lost-response retries; append-only retains history but naive latest-event status can regress",
        "claim_boundary": "Neither approach verifies physical cleanup, authenticated event provenance or legitimate reopening",
    }


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as folder:
        output = run(Path(folder) / "e296.db")
    dest = Path(__file__).parent / "results/e296_revision_cas_vs_append_only.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2))
