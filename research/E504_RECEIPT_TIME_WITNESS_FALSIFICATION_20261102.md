# E504 | A stored receipt timestamp needs an independent comparison field

Date: 2026-11-02. Research-only continuation of E503 on draft PR #54. No production API, database migration, deployment, or main-branch changes.

## Falsifiable question

E503 compared the stored payload to canonical **client evidence**, deliberately excluding `ingested_at` because the client may lie about receipt time. That leaves a specific blind spot: a SQLite writer can alter **only the payload's `ingested_at`** and the existing read/retry consistency gate will still accept the forged timestamp. A stored first-receipt timestamp is therefore not even locally self-consistent under this one-field mutation.

Hypothesis: when the receipt timestamp in the payload and an independently stored `receipt_at` field differ, both `get()` and an exact-ID `put()` retry must reject the record, without overwriting it.

## Change

The unused `ResearchFirstReceiptStore` schema now stores a `receipt_at TEXT NOT NULL` value alongside the payload. Both are written inside the same `BEGIN IMMEDIATE` transaction. The shared `_verified_receipt` check compares the parsed, UTC-normalized payload timestamp against `receipt_at` as well as checking the indexed ID and canonical evidence. The manual E499 process-death writer is updated to use the new four-column schema.

Existing legacy research databases lacking `receipt_at` fail closed on initialization. **Do not silently backfill the new column from the mutable payload:** that would misrepresent the origin of the timestamp. This is an intentionally incompatible *research-only* schema revision, not a production migration.

## Synthetic tests and negative control

1. Modify only `payload.ingested_at`. Expect read and retry to reject.
2. Modify only `receipt_at`. Expect read and retry to reject.
3. **Negative control:** rewrite both timestamp fields consistently. The forged timestamp still passes, proving this is not authentication, anti-rollback protection, or an independent trusted-time witness.
4. Open a legacy three-column research table. Expect an explicit integrity error rather than silent backfill.

## Interpretation and limitations

The added column catches accidental or malicious *single-field* timestamp divergence. It does **not** protect against a database writer who can modify both fields, replay a coherent older database snapshot, forge client identities, or manipulate the process clock. No cryptographic signatures, independent append-only log, trusted monotonic clock, multi-host fencing, power-loss testing, or field validation are claimed.

The decisive next experiment is to bind receipts to a trust anchor **outside the mutable SQLite file**, with explicit key custody and rollback detection. Avoid deploying a local checksum or in-database MAC as though it solved that trust boundary.

## Validation

Source and four deterministic tests committed on the draft research branch. Exact-head GitHub Actions outcomes must be checked independently before reporting success. Preserve failed runs and any negative results.
