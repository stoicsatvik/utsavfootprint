"""E499: research-only first-receipt semantics and their remaining limits."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from utsav_sensor.errors import ObservationConflictError
from utsav_sensor.models import Observation
from utsav_sensor.research_receipt import ResearchFirstReceiptStore

PAST = datetime(2020, 1, 1, tzinfo=UTC)
RECEIVED = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


def report(id="e499-report", **changes):
    data = {
        "id": id,
        "source_type": "citizen",
        "provenance": "observed",
        "source_id": "unverified-citizen",
        "lat": 19.076,
        "lon": 72.8777,
        "observed_at": PAST,
        "ingested_at": PAST,
        "status": "open",
    }
    data.update(changes)
    return Observation(**data)


def test_backdated_client_receipt_is_replaced_by_server_time(tmp_path):
    store = ResearchFirstReceiptStore(tmp_path / "r.db", clock=lambda: RECEIVED)
    stored = store.put(report())
    assert stored.ingested_at == RECEIVED
    assert stored.observed_at == PAST
    assert store.get(stored.id) == stored


def test_retry_with_different_client_receipt_keeps_first_stamp(tmp_path):
    path = tmp_path / "r.db"
    first = ResearchFirstReceiptStore(path, clock=lambda: RECEIVED)
    stamped = first.put(report())
    restarted = ResearchFirstReceiptStore(
        path, clock=lambda: RECEIVED + timedelta(days=3)
    )
    assert restarted.put(report(ingested_at=RECEIVED + timedelta(days=50))) == stamped
    assert restarted.get(stamped.id).ingested_at == RECEIVED


def test_conflicting_evidence_rejected_without_overwrite(tmp_path):
    store = ResearchFirstReceiptStore(tmp_path / "r.db", clock=lambda: RECEIVED)
    original = store.put(report())
    with pytest.raises(ObservationConflictError):
        store.put(report(source_id="different-claimed-source"))
    assert store.get(original.id) == original


def test_independent_connections_concurrent_identical_retries(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "r.db"
    a = ResearchFirstReceiptStore(path, clock=lambda: RECEIVED)
    b = ResearchFirstReceiptStore(path, clock=lambda: RECEIVED + timedelta(seconds=2))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(store.put, report()) for store in (a, b)]
        results = [future.result() for future in futures]
    assert results[0] == results[1]
    assert a.get("e499-report") == results[0]


def test_independent_connections_concurrent_conflict_one_winner(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "r.db"
    a = ResearchFirstReceiptStore(path, clock=lambda: RECEIVED)
    b = ResearchFirstReceiptStore(path, clock=lambda: RECEIVED)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(a.put, report(source_id="A")),
            pool.submit(b.put, report(source_id="B")),
        ]
        results = []
        for future in futures:
            try:
                results.append(future.result())
            except ObservationConflictError as exc:
                results.append(exc)
    assert sum(isinstance(r, ObservationConflictError) for r in results) == 1
    assert sum(isinstance(r, Observation) for r in results) == 1
    assert a.get("e499-report").source_id in {"A", "B"}


def test_clock_timezone_is_normalized(tmp_path):
    offset = timezone(timedelta(hours=5, minutes=30))
    store = ResearchFirstReceiptStore(
        tmp_path / "r.db", clock=lambda: RECEIVED.astimezone(offset)
    )
    assert store.put(report()).ingested_at == RECEIVED


def test_naive_clock_fails_closed_and_can_retry(tmp_path):
    path = tmp_path / "r.db"
    invalid = ResearchFirstReceiptStore(path, clock=lambda: RECEIVED.replace(tzinfo=None))
    with pytest.raises(ValueError, match="aware datetime"):
        invalid.put(report())
    assert invalid.get("e499-report") is None
    restored = ResearchFirstReceiptStore(path, clock=lambda: RECEIVED)
    assert restored.put(report()).ingested_at == RECEIVED


def test_negative_clock_rollback_is_not_prevented(tmp_path):
    """A server timestamp is not a durable monotonic or authenticated clock."""
    path = tmp_path / "r.db"
    a = ResearchFirstReceiptStore(path, clock=lambda: RECEIVED)
    first = a.put(report(id="first"))
    b = ResearchFirstReceiptStore(path, clock=lambda: RECEIVED - timedelta(days=1))
    second = b.put(report(id="second"))
    assert second.ingested_at < first.ingested_at


def test_negative_source_aliases_remain_unauthenticated(tmp_path):
    store = ResearchFirstReceiptStore(tmp_path / "r.db", clock=lambda: RECEIVED)
    one = store.put(report(id="one", source_id="alias-one"))
    two = store.put(report(id="two", source_id="alias-two"))
    assert one.source_id != two.source_id
    # The prototype does not assert these are independent people or sensors.


def _process_put(path, source_id, receipt):
    """Top-level worker for an actual separate-process SQLite writer."""
    store = ResearchFirstReceiptStore(path, clock=lambda: receipt)
    try:
        item = store.put(report(source_id=source_id))
        return ("ok", item.model_dump(mode="json"))
    except ObservationConflictError:
        return ("conflict", None)


def test_cross_process_same_id_conflict_has_single_winner(tmp_path):
    from concurrent.futures import ProcessPoolExecutor
    from multiprocessing import get_context

    path = tmp_path / "r.db"
    # Initialize schema before starting the competing processes.
    ResearchFirstReceiptStore(path, clock=lambda: RECEIVED)
    with ProcessPoolExecutor(max_workers=2, mp_context=get_context("spawn")) as pool:
        a = pool.submit(_process_put, str(path), "A", RECEIVED)
        b = pool.submit(_process_put, str(path), "B", RECEIVED)
        outcomes = [a.result(timeout=20), b.result(timeout=20)]
    assert sorted(status for status, _ in outcomes) == ["conflict", "ok"]
    stored = ResearchFirstReceiptStore(path).get("e499-report")
    assert stored.source_id in {"A", "B"}
    assert stored.ingested_at == RECEIVED


def test_cross_process_identical_retry_preserves_original_receipt(tmp_path):
    from concurrent.futures import ProcessPoolExecutor
    from multiprocessing import get_context

    path = tmp_path / "r.db"
    ResearchFirstReceiptStore(path, clock=lambda: RECEIVED)
    with ProcessPoolExecutor(max_workers=2, mp_context=get_context("spawn")) as pool:
        a = pool.submit(_process_put, str(path), "same", RECEIVED)
        b = pool.submit(_process_put, str(path), "same", RECEIVED + timedelta(days=1))
        outcomes = [a.result(timeout=20), b.result(timeout=20)]
    assert all(status == "ok" for status, _ in outcomes)
    assert outcomes[0][1] == outcomes[1][1]
    assert ResearchFirstReceiptStore(path).get("e499-report").ingested_at in {
        RECEIVED,
        RECEIVED + timedelta(days=1),
    }


def _abrupt_receipt_writer(path, commit):
    """Child exits without Python cleanup immediately before/after COMMIT."""
    import os
    import sqlite3

    from utsav_sensor.research_receipt import _evidence_key

    item = report()
    stamped = item.model_copy(update={"ingested_at": RECEIVED})
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    db.execute("BEGIN IMMEDIATE")
    db.execute(
        "INSERT INTO research_first_receipts(id, evidence, payload) VALUES (?, ?, ?)",
        (item.id, _evidence_key(item), stamped.model_dump_json()),
    )
    if commit:
        db.execute("COMMIT")
    # No context manager or close: this deliberately simulates abrupt process death.
    os._exit(17)


def _run_abrupt_writer(path, *, commit):
    from multiprocessing import get_context

    child = get_context("spawn").Process(
        target=_abrupt_receipt_writer, args=(str(path), commit)
    )
    child.start()
    child.join(timeout=20)
    if child.is_alive():
        child.terminate()
        child.join(timeout=5)
        pytest.fail("abrupt-writer child timed out")
    assert child.exitcode == 17


def test_process_death_before_commit_discards_partial_receipt(tmp_path):
    """SQLite rollback on process death; not a power-loss durability guarantee."""
    path = tmp_path / "r.db"
    store = ResearchFirstReceiptStore(path, clock=lambda: RECEIVED)
    _run_abrupt_writer(path, commit=False)
    assert store.get("e499-report") is None
    assert store.put(report()).ingested_at == RECEIVED


def test_process_death_after_commit_preserves_first_receipt(tmp_path):
    """Committed row survives writer exit; a retry cannot replace its stamp."""
    path = tmp_path / "r.db"
    store = ResearchFirstReceiptStore(path, clock=lambda: RECEIVED + timedelta(days=1))
    _run_abrupt_writer(path, commit=True)
    assert store.get("e499-report").ingested_at == RECEIVED
    assert store.put(report(ingested_at=PAST + timedelta(days=2))).ingested_at == RECEIVED
