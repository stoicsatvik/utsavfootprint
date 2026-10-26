"""E296: SQLite causal revisions, idempotency and append-only failure controls."""
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from research.e296_revision_cas_vs_append_only import (
    append_event,
    cas_mutation,
    initialize,
    run,
    snapshot,
)


def test_delayed_writer_rejected_and_idempotent_ack(tmp_path: Path):
    result = run(tmp_path / "one.db")
    assert result["first_cas"] == {"status": "COMMITTED", "revision": 2}
    assert result["stale_cas"]["status"] == "STALE_REVISION"
    assert result["lost_ack_retry"] == {"status": "REPLAYED_COMMITTED", "revision": 2}
    assert result["idempotency_key_payload_conflict"]["status"] == "IDEMPOTENCY_KEY_CONFLICT"
    assert result["durable"]["revision"] == 2
    assert result["durable"]["status"] == "cleaned"


def test_append_only_preserves_evidence_but_does_not_certify_latest_status(tmp_path: Path):
    result = run(tmp_path / "append.db")
    assert result["durable"]["events"] == [
        ("old-open", "open"), ("cleanup", "cleaned"), ("late-open", "open")]
    assert result["durable"]["last_append_status"] == "open"
    assert not result["duplicate_append_event_inserted"]


def test_two_simultaneous_writers_one_wins(tmp_path: Path):
    path = tmp_path / "race.db"
    with sqlite3.connect(path) as db:
        initialize(db)
    gate = threading.Barrier(2)

    def writer(i: int) -> dict:
        gate.wait(timeout=5)
        return cas_mutation(path, key=f"write-{i}", expected=1, status="cleaned")

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(writer, range(2)))
    assert sorted(x["status"] for x in outcomes) == ["COMMITTED", "STALE_REVISION"]
    assert snapshot(path)["revision"] == 2


def test_crash_before_commit_rolls_back_both_revision_and_receipt(tmp_path: Path):
    path = tmp_path / "crash.db"
    with sqlite3.connect(path) as db:
        initialize(db)
    with sqlite3.connect(path, isolation_level=None) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE state SET revision=2,status='cleaned' WHERE id='shared'")
        db.execute("INSERT INTO mutations VALUES ('attempt','shared',1,'cleaned',2)")
        db.rollback()  # Transaction rollback model, not an actual process crash.
    assert snapshot(path)["revision"] == 1
    assert cas_mutation(path, key="attempt", expected=1, status="cleaned")["status"] == "COMMITTED"


def test_same_event_id_different_payload_does_not_authenticate(tmp_path: Path):
    path = tmp_path / "events.db"
    with sqlite3.connect(path) as db:
        initialize(db)
    assert append_event(path, "e1", "cleaned")
    assert not append_event(path, "e1", "open")
    assert snapshot(path)["events"] == [("e1", "cleaned")]
    # Unique IDs prevent replacement, not forged cleanup assertions.
