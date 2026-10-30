# E416 | SQLite REPLACE bypass of E415 append-only triggers

**30 October 2026. Synthetic database-integrity experiment; no real-world cleanup or tamper-proof provenance claim.**

## Falsifiable failure

E415's opt-in SQLite ledger rejects ordinary `UPDATE` and `DELETE` statements using BEFORE triggers. Does the default SQLite `INSERT OR REPLACE` behavior nevertheless allow an existing receipt to be overwritten without dropping a trigger?

**Yes.** SQLite defaults to `PRAGMA recursive_triggers=OFF`. An `INSERT OR REPLACE` with an existing `sequence` implicitly removes the conflicting row; the DELETE trigger does not fire in that configuration. A minimal reproduction with the E415 table and trigger definitions rejected direct UPDATE/DELETE but allowed a sequence-1 receipt to be rewritten from `original` to `forged`.

This is a negative result for E415's accidental-mutation protection, not evidence of an actual attack on deployed data.

## Bounded correction

`SQLiteRevisionLedger.start()` now creates an additive `BEFORE INSERT` trigger named `revision_no_replace`. It rejects a proposed receipt whose `NEW.sequence` already exists. This check executes before SQLite's conflict-replacement deletion, even with recursive triggers disabled. Existing UPDATE/DELETE triggers remain in place.

- The guard is created with `IF NOT EXISTS`, so reopening an older E415 ledger adds it without rewriting existing receipts.
- Ordinary auto-assigned sequence inserts still succeed.
- The live `SQLiteObservationStore`, API, existing production database and deployments are unchanged.
- A regression test freezes the default-PRAGMA bypass and tests the additive migration.

## Executed validation

A local Python/SQLite source-equivalent harness reproduced the original bypass and passed **5/5** checks: baseline bypass; guarded rejection; legitimate append; idempotent migration; unchanged UPDATE/DELETE protection. The exact trigger SQL was used. The new GitHub regression test file was source-reviewed but **not executed against the complete repository**. No pytest, Ruff, exact-head CI or deployment was run; GitHub Actions had previously exhausted the included 2,000 minutes.

## Remaining negative boundaries

1. A privileged SQLite database owner can drop triggers, edit the file, delete the final receipt or fabricate entirely new rows. This remains an *accidental mutation guard*, not a cryptographic audit system.
2. A missing final suffix remains undetectable without an independently retained trusted head checkpoint.
3. The ledger is opt-in and is not wired into authenticated ingestion. Source/provenance labels remain unauthenticated and prior overwritten observations cannot be recovered.
4. Historical reconstruction still needs full actual-repository integration tests and an independent frozen event-log oracle with late arrivals, corrections, tombstones and missing events.

## Next gate

Run exact-head `pytest` and Ruff locally or after verifying no-charge CI. Then compare persisted replay at frozen cutoffs against an independent oracle and export a verifiable checkpoint outside the SQLite trust boundary. Leave the stacked draft unmerged pending validation.

No email, outreach, paid resource, live database mutation, merge or deployment was made.
