# E499 | Transactional first-receipt prototype, with explicit trust limits

Date: 2026-11-02. Research-only continuation of E498 draft PR #53, stacked on E497 draft PR #52. No production API, persistence schema, deployment, or merge changes.

## Feedback and falsifiable hypothesis

Dr. Alexander Kramida's spectroscopy correspondence was previously acknowledged; no new substantive human replies or PR review comments were found. E498 demonstrated that a public client could backdate `ingested_at` and that claimed source aliases inflated apparent independence. E499 asks a narrower engineering question: **can a server-issued first receipt be stable under exact-ID retries and concurrent, separate SQLite processes without allowing client receipt timestamps to rewrite history?**

## Experimental design

`src/utsav_sensor/research_receipt.py` is an explicitly unused research prototype. It stores canonicalized immutable client evidence (excluding untrusted `ingested_at`) alongside a server-stamped `Observation`. An SQLite `BEGIN IMMEDIATE` transaction serializes the check and first insert across separate connections/processes. On a retry with the same ID and evidence, it returns the original stored receipt; on a conflicting ID, it rejects without overwriting. UTC-aware clock values are required. This is a prototype, not a migration or a public endpoint.

`tests/test_e499_research_first_receipt.py` contains 11 isolated cases:

- Synthetic 2020 client timestamp is replaced with an injected 2026 server clock.
- Exact-ID retries with different client-supplied `ingested_at` return the first stored receipt, including after reopening the database.
- Changed evidence under an existing ID is rejected and preserves the original.
- Independent SQLite connections serialize identical retries and conflicting writes.
- Actual separately spawned processes preserve one winner for conflicting IDs and the same receipt for identical evidence.
- Timezone offsets are normalized to UTC; naive server clock values fail closed.
- **Negative control:** a clock rollback allows a later inserted ID to have an earlier receipt timestamp.
- **Negative control:** distinct anonymous claimed source aliases remain distinct and unauthenticated.

The tests use deterministic injected clocks and synthetic records; they are not measurements from field sensors.

## What this does not establish

1. **Clock authority and monotonicity:** server time can move backwards or be tampered with. No trusted time service or durable global ordering is proven.
2. **Source authenticity:** `source_id` remains caller-supplied; no Sybil resistance or verified issuer identity is claimed.
3. **Cross-host consistency:** SQLite transactions protect one shared database file, not independent hosts, replicas, or partitions. No crash/power-loss durability experiment or distributed fencing is performed.
4. **Production compatibility:** the public `/v1/observations` route and `SQLiteObservationStore` are unchanged. Existing clients may rely on their old timestamp semantics. An omitted `observed_at` may be generated afresh on each request and therefore cause legitimate retries to conflict unless the client preserves the original event timestamp.
5. **Historical migration:** legacy rows containing client-controlled `ingested_at` cannot be retrospectively assigned authentic receipt times without independent evidence.

## Decision gate

Keep this branch draft and unmerged. Before any production change, define a versioned request/response contract, clock authority, migration strategy for existing records, verified issuer identity, and durable multi-process/multi-host storage semantics. Test rollback, crash recovery, clock skew and exact-ID retry behavior under that contract. Do not relabel the existing `independent_sources` metric as authenticated independent reporters.

## Validation

The isolated prototype was exercised locally with a Pydantic-compatible test model: **11/11 tests passed**. This is *not* the full repository suite and does not validate the actual production `Observation` model. GitHub Actions exact-head validation and the full suite must be checked separately; record any failures and do not describe the change as production-ready.
