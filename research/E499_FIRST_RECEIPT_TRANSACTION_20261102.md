# E499 | Transactional first-receipt prototype, with explicit trust limits

Date: 2026-11-02. Research-only continuation of E498 draft PR #53, stacked on E497 draft PR #52. No production API, persistence schema, deployment, or merge changes.

## Feedback and falsifiable hypothesis

Dr. Alexander Kramida's spectroscopy correspondence was previously acknowledged; no new substantive human replies or PR review comments were found. E498 demonstrated that a public client could backdate `ingested_at` and that claimed source aliases inflated apparent independence. E499 asks a narrower engineering question: **can a server-issued first receipt be stable under exact-ID retries and concurrent, separate SQLite processes without allowing client receipt timestamps to rewrite history?**

## Experimental design

`src/utsav_sensor/research_receipt.py` is an explicitly unused research prototype. It stores canonicalized immutable client evidence (excluding untrusted `ingested_at`) alongside a server-stamped `Observation`. An SQLite `BEGIN IMMEDIATE` transaction serializes the check and first insert across separate connections/processes. On a retry with the same ID and evidence, it returns the original stored receipt; on a conflicting ID, it rejects without overwriting. UTC-aware clock values are required. This is a prototype, not a migration or a public endpoint.

`tests/test_e499_research_first_receipt.py` contains 13 isolated cases (11 original plus 2 abrupt-process-exit controls):

- Synthetic 2020 client timestamp is replaced with an injected 2026 server clock.
- Exact-ID retries with different client-supplied `ingested_at` return the first stored receipt, including after reopening the database.
- Changed evidence under an existing ID is rejected and preserves the original.
- Independent SQLite connections serialize identical retries and conflicting writes.
- Actual separately spawned processes preserve one winner for conflicting IDs and the same receipt for identical evidence.
- Timezone offsets are normalized to UTC; naive server clock values fail closed.
- **Negative control:** a clock rollback allows a later inserted ID to have an earlier receipt timestamp.
- **Negative control:** distinct anonymous claimed source aliases remain distinct and unauthenticated.
- Abrupt writer termination before SQLite COMMIT discards the partial row, allowing a clean retry.
- Abrupt writer termination immediately after SQLite COMMIT preserves the original receipt across process death and retry.

The tests use deterministic injected clocks and synthetic records; they are not measurements from field sensors.

## What this does not establish

1. **Clock authority and monotonicity:** server time can move backwards or be tampered with. No trusted time service or durable global ordering is proven.
2. **Source authenticity:** `source_id` remains caller-supplied; no Sybil resistance or verified issuer identity is claimed.
3. **Cross-host consistency:** SQLite transactions protect one shared database file, not independent hosts, replicas, or partitions. A deterministic process-death boundary test is performed, but no power-loss, fsync, storage-controller, or distributed-fencing guarantee is established.
4. **Production compatibility:** the public `/v1/observations` route and `SQLiteObservationStore` are unchanged. Existing clients may rely on their old timestamp semantics. An omitted `observed_at` may be generated afresh on each request and therefore cause legitimate retries to conflict unless the client preserves the original event timestamp.
5. **Historical migration:** legacy rows containing client-controlled `ingested_at` cannot be retrospectively assigned authentic receipt times without independent evidence.

## Decision gate

Keep this branch draft and unmerged. Before any production change, define a versioned request/response contract, clock authority, migration strategy for existing records, verified issuer identity, and durable multi-process/multi-host storage semantics. Test rollback, crash recovery, clock skew and exact-ID retry behavior under that contract. Do not relabel the existing `independent_sources` metric as authenticated independent reporters.

## Validation

The isolated prototype was exercised locally with a Pydantic-compatible test model: **11/11 tests passed**. The actual repository was then validated by [GitHub Actions run #41418689950](https://github.com/stoicsatvik/utsavfootprint/actions/runs/41418689950) at code commit `60d28cb37ad41ece22b50f7c0d5b1bc5ced58941`: **Ruff passed; 195 pytest tests passed, 1 nonfatal Starlette/httpx deprecation warning** (184 inherited, 11 new). The pytest-asyncio fixture-scope configuration also emitted a deprecation notice. Earlier CI attempts [#41418184135](https://github.com/stoicsatvik/utsavfootprint/actions/runs/41418184135), [#41418316281](https://github.com/stoicsatvik/utsavfootprint/actions/runs/41418316281), and [#41418583395](https://github.com/stoicsatvik/utsavfootprint/actions/runs/41418583395) failed Ruff import/style checks before pytest; they were fixed without suppressing lint rules. These results validate the isolated experimental module against the actual `Observation` model, not a production API migration or authenticated evidence. This documentation-only commit requires a separate final-head CI check.

## E500 continuation: abrupt-process-exit falsification (2026-11-02)

A new pair of spawned-child tests uses the **same SQLite table and canonical evidence encoding** as the unused prototype. The child manually executes the insert, then calls `os._exit(17)` without Python cleanup either **before** or **after** `COMMIT`. The parent reopens the store and checks for partial-row visibility, first receipt persistence and retry semantics. These are controlled process-death tests, **not** a crash inside the application's `put()` implementation and **not** simulated power loss. In the pre-commit case, SQLite rolls back the uncommitted row; in the post-commit case, the first stamped row remains readable and the retry retains its original receipt. No production route, store, schema or timestamp policy was changed.

[Exact-head GitHub Actions PR run #41425876723](https://github.com/stoicsatvik/utsavfootprint/actions/runs/41425876723) and [push run #41425867878](https://github.com/stoicsatvik/utsavfootprint/actions/runs/41425867878) **both succeeded** at test commit `aa92ad0999e2f7fa5930b613b7f5f68855ad923e`. The PR job log reports **197 pytest tests passed, one nonfatal Starlette warning**, and Ruff passed. The additional pytest-asyncio configuration warning remains. This validates process termination boundaries only; it cannot establish durability after power loss, disk failure, filesystem reordering, trusted clock ordering, source authentication or multi-host consistency. No new human reply or external outreach prompted these tests.
