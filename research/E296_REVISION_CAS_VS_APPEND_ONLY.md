# E296 | Durable revision CAS versus immutable event history

**Date:** 26 October 2026. Disposable SQLite experiment, synthetic statuses only. This is **not** a production fix, physical-cleanup measurement or authentication system.

## Question

E280 reproduced an older same-ID `open` payload overwriting a newer committed `cleaned` payload across two engines. Which storage primitive addresses the causal and retry failures without claiming that a software record proves real-world cleanup?

Compare two alternatives using actual SQLite transactions, not an in-memory model:

1. A **server-owned integer revision**, atomic `BEGIN IMMEDIATE` compare-and-swap, and a durable mutation-idempotency receipt committed in the same transaction.
2. An **append-only event history** with unique event IDs and a naive latest-arrival status projection.

## Executed synthetic controls

| Scenario | Result |
|---|---|
| Newer `cleaned` CAS from revision 1 | **COMMITTED**, revision 2 |
| Delayed `open` writer still expecting revision 1 | **STALE_REVISION** |
| Same mutation ID retried after hypothetical lost acknowledgement | **REPLAYED_COMMITTED**, revision 2 |
| Same mutation ID reused with different payload | **IDEMPOTENCY_KEY_CONFLICT** |
| Two concurrent SQLite writers expecting revision 1 | **1 COMMITTED / 1 STALE_REVISION** |
| Transaction rolled back before commit | State and receipt both remain at revision 1 |
| Append-only unique event ID replay | Rejected as duplicate |
| Late new-ID `open` event after `cleaned` | History preserved, but naive latest-arrival status **regresses to open** |

These outcomes are deterministic software tests; the transaction rollback control is **not a physical process-crash test**. The append-only counterexample demonstrates that immutable records alone do not establish legitimate causal event order.

## Claim boundaries

**SUPPORTED IN DISPOSABLE SOFTWARE TESTS:** Atomic server-owned revision checks plus a transactionally durable idempotency receipt reject the demonstrated stale writer and acknowledge duplicate delivery without a second update. Append-only identity preserves events but does not certify which status is physically correct.

**NOT YET PROVEN:** A production-safe API, authenticated sources, authorized cleanup/verification, reopening policy, multi-process failure recovery, replication semantics, network retry guarantees, or actual physical cleanup.

**Next decision:** Integrate server-owned revisions and idempotency only after API compatibility, migration, failure injection and authorization are specified; keep an append-only audit history separate from current-state projection. Do not infer that a synthetic `cleaned` string establishes real cleanup.

Reproduce: `pytest -q tests/test_e296_revision_cas_vs_append_only.py`; `python -m research.e296_revision_cas_vs_append_only`. The workflow preserves a machine-readable receipt without persisting a database.
