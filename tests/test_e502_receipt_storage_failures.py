"""E502: storage-failure falsification of the unused first-receipt prototype.

The SQLITE_FULL case uses SQLite's real max_page_count enforcement, not a
mocked insert error. The COMMIT case injects an exception to check rollback
when SQLite has not itself rolled back. Neither simulates a power cut.
"""

import sqlite3
from datetime import UTC, datetime

import pytest

import utsav_sensor.research_receipt as receipt_module
from utsav_sensor.models import Observation
from utsav_sensor.research_receipt import ResearchFirstReceiptStore

RECEIVED = datetime(2026, 11, 2, 9, tzinfo=UTC)


def report(observation_id: str, **changes) -> Observation:
    values = {
        "id": observation_id,
        "source_type": "citizen",
        "provenance": "observed",
        "source_id": "unverified",
        "lat": 19.076,
        "lon": 72.8777,
        "observed_at": RECEIVED,
        "ingested_at": RECEIVED,
        "status": "open",
    }
    values.update(changes)
    return Observation(**values)


def test_real_sqlite_full_preserves_error_and_existing_receipt(tmp_path, monkeypatch):
    path = tmp_path / "receipts.db"
    store = ResearchFirstReceiptStore(path, clock=lambda: RECEIVED)
    original = store.put(report("stable"))
    real_connect = sqlite3.connect

    def capped_connect(*args, **kwargs):
        db = real_connect(*args, **kwargs)
        if kwargs.get("isolation_level") is None:
            pages = db.execute("PRAGMA page_count").fetchone()[0]
            assert db.execute(f"PRAGMA max_page_count = {pages}").fetchone()[0] == pages
        return db

    # A 100 KB payload cannot fit within the existing database page count.
    # SQLite raises SQLITE_FULL and may auto-rollback before the exception handler.
    with monkeypatch.context() as patch:
        patch.setattr(receipt_module.sqlite3, "connect", capped_connect)
        with pytest.raises(sqlite3.OperationalError) as failure:
            store.put(report("too-large", metadata={"padding": "x" * 100_000}))
    assert failure.value.sqlite_errorcode == sqlite3.SQLITE_FULL
    assert store.get("stable") == original
    assert store.get("too-large") is None
    # Removing the artificial capacity cap allows a clean retry.
    assert store.put(report("too-large", metadata={"padding": "x" * 100_000}))


def test_injected_commit_failure_rolls_back_and_preserves_cause(tmp_path, monkeypatch):
    path = tmp_path / "receipts.db"
    store = ResearchFirstReceiptStore(path, clock=lambda: RECEIVED)
    real_connect = sqlite3.connect

    class FailingCommitConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql.strip().upper() == "COMMIT":
                raise sqlite3.OperationalError("injected commit failure")
            return super().execute(sql, parameters)

    def failing_connect(*args, **kwargs):
        if kwargs.get("isolation_level") is None:
            return real_connect(*args, factory=FailingCommitConnection, **kwargs)
        return real_connect(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(receipt_module.sqlite3, "connect", failing_connect)
        with pytest.raises(sqlite3.OperationalError, match="injected commit failure"):
            store.put(report("failed-commit"))
    assert store.get("failed-commit") is None
    assert store.put(report("failed-commit")).ingested_at == RECEIVED
