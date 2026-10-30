# E430 | Mixed-offset SQLite chronology and earlier timezone work

**Date:** 2026-10-30. **Scope:** E429 draft PR #45, no merge or deployment.

## Falsified ordering assumption

SQLite `ORDER BY observed_at DESC` compares stored ISO-8601 TEXT lexicographically, not as UTC instants. The original E429 model accepted and preserved explicit offsets; the 2026-10-31 reconciliation now canonicalizes newly validated observations to UTC. Legacy mixed-offset SQLite rows can still exist. In a deterministic SQLite reproduction:

| ID | Stored observed_at | Actual UTC instant |
| --- | --- | --- |
| older | `2026-10-30T17:30:00+05:30` | 12:00Z |
| newer | `2026-10-30T12:30:00+00:00` | 12:30Z |

**Pre-fix SQL order:** `older, newer`. **Correct order:** `newer, older`. This is a real deterministic ordering defect in the SQLite adapter contract, **not** evidence of a production incident. The engine currently re-sorts observations after loading, but direct `SQLiteObservationStore.all()` consumers see the wrong order.

## Minimal change

- Load the existing JSON payloads, validate them as `Observation`, and sort by the aware `observed_at` instant, with `id` as a deterministic tie-breaker.
- Validate legacy mixed-offset payloads and normalize them **in memory** to UTC; do not guess missing timezones, mutate stored rows, alter the database schema, or silently repair malformed legacy rows.
- The revised `test_sqlite_store_orders_legacy_mixed_offsets_by_instant` inserts raw legacy SQLite rows with different offsets, preserves the incorrect SQL TEXT ordering as a negative control, and verifies corrected in-memory chronology.

## Independent prior art and integration conflict

**This work is not the first timezone correction in this repository.** Existing unmerged draft PR [#11 (E175)](https://github.com/stoicsatvik/utsavfootprint/pull/11) already rejects naive timestamps **and normalizes aware values to UTC**; its exact-head CI passed 40 tests. Draft PR [#12 (E176)](https://github.com/stoicsatvik/utsavfootprint/pull/12) already provides a **read-only legacy SQLite timestamp audit**; its exact-head CI passed 45 tests.

**Reconciled on the E429/E430 draft branch on 2026-10-31:** E429 now uses E175's canonical UTC policy, while E430 retains its defensive legacy mixed-offset sorting. This does not merge E175 or E176, and does not imply compatibility of the entire stacked series. Reuse E176 and E177's existing read-only audits; do not implement a duplicate audit or merge both stacks blindly.

## Validation and remaining gates

- Original SQL misordering reproduced locally.
- **4/4 isolated source-equivalent Python 3/Pydantic 2.13.5/SQLite/pytest checks passed:** original misordering, corrected ordering, deterministic equal-instant tie, preserved +05:30 offset, and fail-closed naive legacy loading (four test functions; first includes old and new behavior).
- **Actual repository pytest, Ruff, exact-head GitHub CI: NOT RUN.** Included Actions minutes were exhausted per the 2026-10-29 billing notice. Commits use `[skip ci]` to avoid potentially billable runs.
- **2026-10-31 follow-up:** 5/5 source-equivalent Pydantic/SQLite local checks passed for UTC normalization, naive rejection, and legacy mixed-offset chronology. Exact repository tests/Ruff/CI remain **NOT RUN**.
- No production database was accessed. Before merge, run the complete tests in verified no-charge capacity, audit an authorized offline snapshot with E176/E177, and review any existing offset-dependent clients. No automatic data migration or backfill was attempted.

## Broader stack duplication found during 2026-10-31 review

The timezone conflict is not isolated. The earlier unmerged [E177 PR #13](https://github.com/stoicsatvik/utsavfootprint/pull/13) already added non-finite material-probability rejection and legacy payload audit coverage; the later stacked [E423 PR #40](https://github.com/stoicsatvik/utsavfootprint/pull/40) addresses the same material-NaN input invariant. Likewise, earlier [E187 PR #14](https://github.com/stoicsatvik/utsavfootprint/pull/14) already added `allow_inf_nan=False` for input mass bounds, overlapping later [E424 PR #41](https://github.com/stoicsatvik/utsavfootprint/pull/41).

These are **independent draft branches, not merged changes**. The older exact-head green CI results do not validate the later stack. Before integration, build a per-file/per-invariant comparison, select one implementation per contract, and retain whichever regression tests and audit safeguards provide nonredundant coverage. Do not cherry-pick both implementations blindly. This is an integration finding, not an additional code change or a claim that the full stacks are equivalent.
