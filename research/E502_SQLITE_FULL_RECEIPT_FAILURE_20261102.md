# E502 | Real SQLite capacity exhaustion and first-receipt failure boundaries

Date: 2026-11-02. Continuation of E499-E501 in draft PR #54. This change affects only the unused research first-receipt prototype and its tests. No production endpoint, database migration, deployment, or merge.

## Question and hypothesis

E501 established synthetic process-death behavior around actual `put()` COMMIT calls. It did not test storage errors. **Hypothesis:** SQLite capacity exhaustion may automatically roll back the active transaction, causing the prototype's unconditional SQL `ROLLBACK` to fail and mask the original `SQLITE_FULL` error. A separate injected COMMIT failure should still roll back the uncommitted receipt.

## Reproduction and change

A direct Python SQLite experiment with a real database, a page-count cap set using `PRAGMA max_page_count`, and a 100 KB insert produced `OperationalError: database or disk is full` with `Connection.in_transaction == False`. Issuing SQL `ROLLBACK` then raised a **different** `OperationalError: cannot rollback - no transaction is active`. Thus the original failure was masked in the previous `ResearchFirstReceiptStore.put()` exception path.

The prototype now checks `db.in_transaction` before calling `db.rollback()`. If cleanup itself fails, the original exception is retained; closing the connection remains the final cleanup boundary. This is a diagnostic/correctness fix, not proof of physical storage durability.

`tests/test_e502_receipt_storage_failures.py` adds two cases:

1. **Real SQLite capacity limit:** after preserving a valid receipt, cap the existing database page count for the write connection, attempt a 100 KB observation, require the original `SQLITE_FULL` code, verify no partial row or alteration to the prior receipt, then lift the artificial limit and retry.
2. **Synthetic COMMIT error:** inject a COMMIT exception on the actual `put()` connection while its transaction remains active, require the original exception, verify rollback, and verify a later clean retry.

The direct SQLite reproduction above was executed locally. Full repository tests and GitHub Actions validation for the committed implementation are tracked separately and must not be inferred from that reproduction.

## Remaining negative boundaries

- A page-count cap is deterministic capacity exhaustion, **not** a real device running out of disk space, power failure, controller-cache flush, or filesystem durability proof.
- The COMMIT failure is injected before SQLite executes COMMIT. A native mid-COMMIT I/O error may have different transaction state.
- Suppressing a rollback-cleanup exception preserves the original failure for diagnosis but does not prove that cleanup succeeded; a failed close or broken storage device still requires operational handling.
- Issuer authenticity, trusted time, Sybil resistance, multi-host consistency and historical migration remain unresolved.

## Gate

Keep PR #54 draft. Validate Ruff and full pytest on the exact head. No production integration until a versioned receipt contract, authenticated issuers, trusted time, and real deployment/storage recovery requirements are established.
