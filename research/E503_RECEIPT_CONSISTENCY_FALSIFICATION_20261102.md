# E503 | SQLite receipt consistency is not authenticated provenance

Date: 2026-11-02. Continuation of E499-E502 in draft PR #54, without production API, schema migration, deployment, or merge changes.

## Question

E502 established that an unused SQLite first-receipt prototype preserves its original storage failure. E503 asks whether an already stored receipt can silently contradict its canonical evidence or its indexed observation ID.

**Falsifiable hypothesis:** changing only one of the SQLite evidence/payload fields, or changing the payload's observation ID, must make both `get()` and an exact-ID `put()` retry fail closed without silently returning or rewriting an inconsistent receipt.

## Implementation and controls

The research-only `ResearchFirstReceiptStore` now checks that the decoded stored payload's `id` matches the lookup key and that its canonical client evidence matches the stored evidence string. Both `get()` and the existing-row path of `put()` use the same check, raising `ResearchReceiptIntegrityError` on mismatch. A client-evidence conflict is still handled separately as `ObservationConflictError` after the persisted row passes its own consistency check.

`tests/test_e503_receipt_integrity.py` adds three synthetic SQLite mutations:

1. Replace only the stored evidence with an unrelated JSON string. Expect both read and retry to reject and preserve the altered row for diagnosis.
2. Replace only the stored payload with an otherwise valid observation carrying a different ID. Expect both read and retry to reject.
3. **Negative control:** rewrite both evidence and payload coherently to impersonate a different source. The consistency check accepts the forged pair, demonstrating that consistency is **not** authentication.

These are direct local database mutations, not evidence of an externally exploitable public API. This is not a cryptographic MAC, signature, secure database, trusted clock, or anti-Sybil system. An attacker with database write access can alter both columns; database snapshots, storage corruption, and SQLite `PRAGMA integrity_check` are separate questions. No trusted historical migration or multi-host guarantee is claimed.

## Decision

Keep draft PR #54 unmerged. A future authenticated issuer or tamper-evident log requires an independent trust anchor, key custody, and anti-rollback semantics. Do not promote this row-consistency diagnostic into a provenance or durability claim.

## Validation status

The new source and tests were committed on the research branch. Exact-head GitHub Actions Ruff/pytest outcomes must be checked independently; this document does not claim they passed before verification.
