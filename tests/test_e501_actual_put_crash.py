"""E501: process-death probes at actual ResearchFirstReceiptStore.put() commits.

The wrapper is confined to a spawned child. No production or research-store
implementation is patched on disk, and no power-loss durability is claimed.
"""

from datetime import UTC, datetime, timedelta
from multiprocessing import get_context

import pytest

from utsav_sensor.models import Observation
from utsav_sensor.research_receipt import ResearchFirstReceiptStore

RECEIVED = datetime(2026, 11, 2, 9, tzinfo=UTC)
PAST = datetime(2020, 1, 1, tzinfo=UTC)


def _report():
    return Observation(
        id="e501-report",
        source_type="citizen",
        provenance="observed",
        source_id="unverified-citizen",
        lat=19.076,
        lon=72.8777,
        observed_at=PAST,
        ingested_at=PAST,
        status="open",
    )


def _crash_during_actual_put(path: str, phase: str):
    """Exit from the real put() call immediately before/after its COMMIT."""
    import os

    import utsav_sensor.research_receipt as receipt_module

    real_connect = receipt_module.sqlite3.connect

    class CrashConnection:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, sql, *args, **kwargs):
            if sql.strip().upper() == "COMMIT" and phase == "before_commit":
                os._exit(17)
            result = self.connection.execute(sql, *args, **kwargs)
            if sql.strip().upper() == "COMMIT" and phase == "after_commit":
                os._exit(17)
            return result

        def close(self):
            return self.connection.close()

        def __getattr__(self, name):
            return getattr(self.connection, name)

    receipt_module.sqlite3.connect = lambda *a, **kw: CrashConnection(
        real_connect(*a, **kw)
    )
    receipt_module.ResearchFirstReceiptStore(path, clock=lambda: RECEIVED).put(
        _report()
    )
    os._exit(91)  # If this fires, the expected COMMIT boundary was not reached.


def _run_crash(path, phase):
    child = get_context("spawn").Process(
        target=_crash_during_actual_put, args=(str(path), phase)
    )
    child.start()
    child.join(timeout=20)
    if child.is_alive():
        child.terminate()
        child.join(timeout=5)
        pytest.fail("actual-put crash child timed out")
    assert child.exitcode == 17


def test_actual_put_process_death_before_commit_rolls_back(tmp_path):
    path = tmp_path / "receipts.db"
    store = ResearchFirstReceiptStore(path, clock=lambda: RECEIVED)
    _run_crash(path, "before_commit")
    assert store.get("e501-report") is None
    assert store.put(_report()).ingested_at == RECEIVED


def test_actual_put_process_death_after_commit_preserves_receipt(tmp_path):
    path = tmp_path / "receipts.db"
    store = ResearchFirstReceiptStore(
        path, clock=lambda: RECEIVED + timedelta(days=1)
    )
    _run_crash(path, "after_commit")
    assert store.get("e501-report").ingested_at == RECEIVED
    assert store.put(_report()).ingested_at == RECEIVED
