# E265: Committed SQLite read-through across independent sensor engines

## E252 counterexample and hypothesis

E252 demonstrated that two independently instantiated `SensorEngine` objects sharing one SQLite database could report contradictory states after a completed write. An instance-local `asyncio.Lock` does not invalidate another instance's cached observations.

**Hypothesis:** replacing the SQLite-backed observation read path with a committed database snapshot on every read should remove this particular post-commit stale-cache failure, without changing mock/in-memory stores.

## Implementation

- `SQLiteObservationStore.read_snapshot()` exposes a fresh, single-SELECT committed SQLite snapshot; the implementation deliberately does not claim a cross-process cache invalidation protocol.
- `SensorEngine.observations()` opts into that read-through only when the backing store exposes `read_snapshot`, under its existing local ordering lock. Hotspots and source health use the same path.
- Existing E252 synthetic tests now require two engine instances to observe each other's completed writes, both for the same observation ID and disjoint IDs.
- A new test commits a replacement synthetic record in an **independent Python process**, then reads it through the original live engine without restarting.
- A separate test corrupts committed JSON in disposable SQLite and requires both observations and hotspots to raise rather than silently returning old cached data.

## Evidence and limitations

The test cases use disposable local SQLite databases and synthetic observations, **not** real cleanup events or real sensors. The read-through strategy pays O(N) per read and may be unsuitable for large datasets. A read overlapping a write can legitimately observe the earlier committed snapshot. This is not a multi-replica distributed consistency guarantee, and no external Postgres/Supabase adapter was tested.

**Claim:** Post-commit SQLite cross-instance read visibility SUPPORTED only if the exact-head tests pass. Multi-process high-contention performance, transactional revision invalidation, write conflict policy, and real observation authenticity NOT YET PROVEN.

**Next:** compare this correct but O(N) reference against a transactional revision-indexed cache with adversarial writer/reader interleavings, crash recovery, and performance measurements. Keep E252 negative evidence in its original branch/report. No deployment, live data, merge, outreach, or field operations.
