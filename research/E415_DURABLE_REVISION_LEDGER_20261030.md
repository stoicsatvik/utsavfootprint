# E415 | Opt-in durable revision receipts for historical hotspot reconstruction

**30 October 2026. Synthetic software-integrity experiment. No verified physical cleanup evidence.**

## Problem and falsifiable hypothesis

E414 proved that the live `SQLiteObservationStore` overwrites earlier observations with
`ON CONFLICT(id) DO UPDATE`, losing historical corrections. Its in-memory
`ObservationRevision` helper can replay a complete history but has no durable
source of receipts. Hypothesis: a separate, transactional SQLite append-only
ledger can preserve corrections and tombstones across process restarts, assign
ordered receipts at write time, and reject accidental record edits and
known-incomplete logs, **without altering the live ingestion path**.

## Bounded implementation

- `src/utsav_sensor/revision_store.py` introduces opt-in `SQLiteRevisionLedger`.
  Its database path is caller-selected; no live database migration or API
  integration occurs.
- `append()` snapshots and validates the supplied observation, assigns a
  server-side UTC receipt and SQLite sequence in one `BEGIN IMMEDIATE`
  transaction, and supports explicit deletion tombstones.
- SQLite UPDATE/DELETE triggers reject accidental revision modification.
  A backwards wall-clock jump or future ingestion timestamp is rejected.
- `revisions()` validates the complete history through E414 replay, and an
  optional `expected_head_sequence` detects a missing suffix **only when the
  caller supplies a trusted, independently retained head checkpoint**.
- `hotspots_as_of()` uses E414's strict replay and E413's historical fusion.
  Current live upserts and public hotspot responses are unchanged.

## Local validation actually executed

- Four isolated pytest checks passed with the **new module's source** and
  a minimal Pydantic `Observation` / E414 replay mirror: durable correction
  and deletion across restart; bad input and SQL mutation rejection; twelve
  concurrent appends with contiguous sequence; and suffix deletion detected
  only when a previously retained head sequence was supplied.
- Python compileall passed on the isolated module.
- These are **not** exact repository pytest, Ruff, database migration,
  integration, or GitHub Actions results. Full repository dependencies and
  the actual E414 fusion implementation were not executed in this harness.
- The earlier E414 negative SQL-overwrite finding is unchanged.

## Explicit failure and security boundaries

1. An administrator with write access to the SQLite file can drop triggers,
   rewrite rows, or truncate the ledger. There is no cryptographic hash chain,
   external timestamp authority, signature, or independently verified
   checkpoint. A missing suffix is undetectable without an external head.
2. Receipts are issued by this local process, not by an authenticated remote
   ingestion service. `source_id`, `provenance`, and claimed cleanup status
   remain unverified labels.
3. The ledger is opt-in and **not wired into the live store**. It does not
   reconstruct records already overwritten before the ledger was enabled.
4. Sequence order is atomic for this SQLite file, but clock rollback causes
   append failure rather than silently assigning misleading timestamps.
5. GitHub Actions minutes were previously exhausted (2,000/2,000 on
   29 October). No manual CI, paid run, deployment, or merge was initiated.

## Next gate

Run exact-head repository pytest/Ruff and a restart/concurrency integration
test with the actual E414 model and fusion code. Independently freeze a
revision-log oracle including late arrivals, corrections, tombstones, same-time
receipts, missing interior events and a missing tail. Before any production
audit claim, integrate authenticated server-side ingestion and export
cryptographically verifiable checkpoints outside the SQLite trust boundary.

No email, outreach, legal/data-sharing commitment or live database change was made.
