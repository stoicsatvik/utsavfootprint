# E252 | Two independently instantiated engines over one SQLite database

**Date:** 2026-10-25. **Claim:** multi-engine cache consistency REJECTED for the current in-memory design, under deterministic real SQLite tests. No production database, live sensor, field measurement or actual cleanup event.

## Question

Does E235's per-engine lock make two separate `SensorEngine` instances consistent when they share the same durable SQLite observation store?

**No.** E235's ordering boundary is local to one engine instance. The SQLite upsert is durable, but another engine's `_observations` dictionary is not invalidated.

## Reproducible experiments

The new tests use two `SQLiteObservationStore` objects pointed at the same disposable `tmp_path` database, and two independently instantiated engines.

1. **Same-ID conflicting statuses:** Engine A ingests synthetic observation `shared` with source `first`, status `open`. Engine B subsequently ingests `shared` with source `second`, status `cleaned`. SQLite correctly retains the second value, but A still reports `first/open`, while B reports `second/cleaned`. A's explicit restart/reload recovers the durable value. This is a simulated status, **not evidence of any legitimate cleanup**.
2. **Disjoint IDs:** A ingests `first-id` and B ingests `second-id`. SQLite holds both, but each engine exposes only its locally ingested ID. Explicit reloads reconcile both.

These are deterministic **sequential** interleavings. No rare timing race is needed. SQLite itself is not shown to have lost any write. Passing tests intentionally preserve unsafe behavior; they must not be interpreted as a fix.

## Interpretation

- E235's single-instance serialization remains SUPPORTED.
- Multi-instance read consistency is **REJECTED** under the tested architecture.
- Even if all writes are durable, separate worker caches can disagree about observation status and hotspot inputs.
- Adding a process-local lock or a simple SQLite transaction around `upsert` cannot invalidate other processes' caches.
- The test does not demonstrate actual multi-process timing, external sensor truth, source authentication, crash safety or production-scale behavior.

## Next discriminating experiment

Add a durable monotonically increasing observation revision or database change counter, then test explicit read-through/version-checked refresh against two independent processes. Preserve the E235 in-process ordering tests and the E199 unauthenticated-cleanup vulnerability as separate gates. A revision check before reading alone may still race a subsequent write; do not claim linearizability without an atomic snapshot/read contract. No production multi-worker deployment before these gates.

**Evidence:** `tests/test_e252_cross_instance_sqlite_staleness.py` and its exact-head GitHub Actions run.
