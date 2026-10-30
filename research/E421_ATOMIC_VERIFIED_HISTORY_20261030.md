# E421 | Atomic verified historical reads

**30 October 2026. Synthetic SQLite evidence only. No live ingestion, deployment, merge, or authenticated cleanup claim.**

## Falsifiable question

E417 exposes `verify_checkpoint(expected_head, expected_digest)` and E415 exposes `revisions()` / `hotspots_as_of()`. Does verifying the digest and then reading historical observations in separate calls actually bind the returned observations to the verified bytes?

**No.** A change between the two calls can make the first verification pass while the later read returns different data. This is a time-of-check/time-of-use (TOCTOU) gap, even if the expected checkpoint is independently retained. It is not evidence that an attacker accessed a real database.

## Negative reproduction

A local standalone SQLite/Python experiment created one synthetic open receipt, verified its checkpoint, changed the row to cleaned, then read the row. The earlier verification passed; the later read returned `cleaned`; recomputing the digest detected the mismatch. This reproduces the split-check gap without a real cleanup event. A privileged database writer was deliberately assumed.

## Implementation

- Added opt-in `SQLiteRevisionLedger.verified_revisions(expected_head_sequence, expected_sha256)`.
- A single SQLite read transaction obtains the raw rows and hashes the exact same row snapshot that is then parsed into revision objects.
- Uses the E417 domain separator, length framing, contiguous-sequence validation, and constant-time digest comparison.
- Rejects malformed expected checkpoints and mismatches before returning any revisions.
- Added `verified_hotspots_as_of(as_of, expected_head_sequence, expected_sha256)` to construct historical hotspots only from a verified in-memory snapshot.
- Existing unverified methods, live API, database schema and ingestion paths remain unchanged.

## Regression contracts

`tests/test_e421_atomic_verified_snapshot.py` contains two repository tests:

1. A deterministic split-check counterexample using a privileged SQLite payload rewrite, followed by a required mismatch from both new verified methods.
2. A ten-event, three-site correction/deletion/recreation trace. At each recorded cutoff, compare verified historical hotspot status against an independent dictionary event-log oracle. Reopen SQLite, verify stable checkpoint, append one more receipt, and require rejection of the stale checkpoint.

**Validation status:** The standalone SQLite TOCTOU counterexample passed locally. The new repository pytest tests, Ruff, and exact-head CI have **not yet been executed or confirmed**. E420's earlier 66/66 CI success applies to its earlier commit, not E421.

## Limitations

- A checkpoint must be retained independently. A compromised expected checkpoint or malicious writer acting before its creation defeats this comparison.
- This does not authenticate observation provenance, physical cleanup, sensor identity, or ingestion timestamps.
- This validates one consistent SQLite read snapshot. It does not prevent later appends; callers must request a new checkpoint to see newly appended evidence.
- A complete independent event-log oracle test is committed but not yet verified against the repository environment.
- No previous overwritten history can be recovered.

## Next gate

Run exact-head `ruff check src tests scripts` and `pytest -q` when the workflow can execute without unapproved charges. Review the stacked E413-E421 branch chain before any merge. Independent checkpoint custody and authenticated source ingestion remain separate research requirements.
