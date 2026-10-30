# E430 | Mixed-offset SQLite chronology and earlier timezone work

**Date:** 2026-10-30. **Scope:** E429 draft PR #45, no merge or deployment.

## Falsified ordering assumption

SQLite `ORDER BY observed_at DESC` compares stored ISO-8601 TEXT lexicographically, not as UTC instants. The E429 model accepts and preserves explicit offsets. In a deterministic SQLite reproduction:

| ID | Stored observed_at | Actual UTC instant |
| --- | --- | --- |
| older | `2026-10-30T17:30:00+05:30` | 12:00Z |
| newer | `2026-10-30T12:30:00+00:00` | 12:30Z |

**Pre-fix SQL order:** `older, newer`. **Correct order:** `newer, older`. This is a real deterministic ordering defect in the SQLite adapter contract, **not** evidence of a production incident. The engine currently re-sorts observations after loading, but direct `SQLiteObservationStore.all()` consumers see the wrong order.

## Minimal change

- Load the existing JSON payloads, validate them as `Observation`, and sort by the aware `observed_at` instant, with `id` as a deterministic tie-breaker.
- Preserve the original explicit UTC offsets; do not guess a timezone, mutate records, alter the database schema, or silently repair malformed legacy rows.
- Add `test_sqlite_store_orders_offsets_by_instant_not_wall_clock` to the E429 regression module.

## Independent prior art and integration conflict

**This work is not the first timezone correction in this repository.** Existing unmerged draft PR [#11 (E175)](https://github.com/stoicsatvik/utsavfootprint/pull/11) already rejects naive timestamps **and normalizes aware values to UTC**; its exact-head CI passed 40 tests. Draft PR [#12 (E176)](https://github.com/stoicsatvik/utsavfootprint/pull/12) already provides a **read-only legacy SQLite timestamp audit**; its exact-head CI passed 45 tests.

E429 overlaps E175's rejection contract but deliberately **preserves** incoming offsets rather than normalizing them. The integration strategy must select one canonical policy, reconcile the divergent tests, and reuse E176's audit rather than implementing another. Do not merge both stacks blindly.

## Validation and remaining gates

- Original SQL misordering reproduced locally.
- **4/4 isolated source-equivalent Python 3/Pydantic 2.13.5/SQLite/pytest checks passed:** original misordering, corrected ordering, deterministic equal-instant tie, preserved +05:30 offset, and fail-closed naive legacy loading (four test functions; first includes old and new behavior).
- **Actual repository pytest, Ruff, exact-head GitHub CI: NOT RUN.** Included Actions minutes were exhausted per the 2026-10-29 billing notice. Commits use `[skip ci]` to avoid potentially billable runs.
- No production database was accessed. Before merge, run the complete tests in verified no-charge capacity, run E176 against an authorized offline DB snapshot, and choose UTC normalization vs offset preservation.
