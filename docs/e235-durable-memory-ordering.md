# E235: Durable observation/cache ordering under concurrent ingestion

## Question and falsification

Can an asynchronous sensor engine report a different observation for the same ID
than the observation durably stored, even when both storage operations succeed?

**Yes, before this change.** Two independent, deterministic disposable-store
interleavings reproduced two defects:

1. **Concurrent upsert reorder:** a first write reached the store, then paused
   before returning. A second write for the same ID persisted and published.
   When the first resumed, the cache reverted to the first value while the
   durable store retained the second. The test observed
   `cache.source_id == "first"` versus `store.source_id == "second"`.
2. **Startup snapshot overwrite:** startup read an empty snapshot and paused.
   A concurrent ingest persisted and published a new observation. Startup then
   resumed and replaced the cache with the stale empty snapshot.

The test-first commit was `a93944ffb92bb4013cb07cef8bfeb14e172488b6`.
Exact-head Actions [40134418881](https://github.com/stoicsatvik/utsavfootprint/actions/runs/40134418881)
failed the **two new regressions**, with **19 existing tests passing** and
Ruff passing. This is a software concurrency result, not physical sensor data.

## Correction

The same `SensorEngine._lock` now protects each complete
`store.upsert -> cache publication` operation and the complete
`store.start -> store.all -> cache initialization` sequence.

This gives an **in-process ordering boundary** for operations using the same
engine instance. A failed durable upsert does not publish a cache update.

Fix commit: `6eea1c2b5adbe1a4d62f7ad3d7b1d134c1991321`.
Exact-head Actions [40134471541](https://github.com/stoicsatvik/utsavfootprint/actions/runs/40134471541)
passed **21/21 tests** and Ruff.

## Claim boundary

**SUPPORTED in deterministic in-process synthetic concurrency tests.**

Not established: cross-process or multi-replica linearizability, database
transaction isolation across independently instantiated engines, crashes or
power-loss durability, live API request ordering, source authentication,
cleanup legitimacy, or real waste-mass accuracy.

The lock intentionally spans awaited storage I/O. This trades ingestion
throughput for consistency in the current local-first engine. Measure
contention and consider database-level revision/compare-and-swap semantics
before adding multiple workers.

## Next discriminating test

Run a two-engine SQLite replay with the same ID, deliberately delayed writes
and restarts. Test whether a revision/fencing mechanism is necessary for
cross-instance consistency. Separately address the E199 unauthenticated
cleanup-status vulnerability before any real operational use.

No production database, sensor, deployment or main branch was changed.
This draft PR is stacked on E199 PR #19.
