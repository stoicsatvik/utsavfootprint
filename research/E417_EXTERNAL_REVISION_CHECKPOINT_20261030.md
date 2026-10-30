# E417 | Independently retained checkpoint for SQLite revision receipts

**30 October 2026. Synthetic integrity tests only. No authenticated physical cleanup or tamper-proof storage claim.**

## Prior negative result and falsifiable question

E415-E416 prevent common accidental SQL mutations, but a privileged SQLite owner can drop triggers, rewrite a receipt, or delete a final suffix. E415's optional expected-head **count** detects a deleted suffix only if an external party remembers the old head; it does not detect a same-length payload rewrite. Can a read-only, deterministic digest of the complete raw ledger detect either change **when the expected digest is retained outside the SQLite trust boundary**?

## Implementation

- Opt-in `SQLiteRevisionLedger.checkpoint()` returns `(head_sequence, sha256_hex)`, without writing to the database or another service.
- Hash input is domain-separated (`utsav-revision-ledger-checkpoint-v1` followed by a null byte) and streams each ordered raw SQLite row as UTF-8 JSON with an eight-byte length prefix. This binds sequence, receipt timestamp, observation ID, and exact stored payload bytes.
- One explicit SQLite read transaction supplies a consistent snapshot. Sequence gaps and missing prefixes fail closed.
- `verify_checkpoint(expected_head_sequence, expected_sha256)` rejects malformed expectations and raises on either head or digest mismatch, using constant-time digest comparison.
- No live ingestion, storage schema, production API, external communication, or deployment is changed. No external checkpoint is automatically stored.

## Executed local experiment

A standalone Python/SQLite harness reproducing the exact row serialization, domain separator and comparison logic passed **5/5** synthetic checks: deterministic reopen, equal-length payload tampering, missing suffix, sequence-gap rejection and malformed expected digest. This harness did **not** execute the complete repository implementation.

Repository regression contracts were committed for restart stability, changed-head detection, privileged same-length row rewriting, suffix deletion, missing-prefix rejection and invalid expected inputs. **These repository tests, full pytest, Ruff and exact-head GitHub CI were not executed** because the Actions account had reported 2,000/2,000 included minutes consumed. The harness does not validate the Pydantic model/fusion integration.

## Explicit limitations and negative results

1. The digest is **not a signature**. A privileged attacker who can change both the ledger and the expected checkpoint can forge agreement. A locally retained checkpoint or a checkpoint stored in the same database provides no independent protection.
2. A checkpoint proves only consistency with the previously retained bytes, not source authenticity, real-world cleanup, observation accuracy, or an independent timestamp. This implementation does not transmit, publish, timestamp or anchor receipts.
3. A fresh checkpoint generated *after* corruption simply hashes the corrupted state. Detection requires a trusted earlier off-database value.
4. No historical events overwritten before E415 can be recovered. The ledger remains opt-in.
5. The digest format is versioned by a fixed prefix. Any serialization change requires a new version and independent compatibility tests.
6. There is no demonstrated protection against a privileged database owner without independent custody of the expected digest.

## Next gate

Run the exact repository pytest/Ruff suite locally or when CI is confirmed no-cost. Then validate exported checkpoints across process restarts, late arrivals, corrections and tombstones against an independent frozen event-log oracle. Design authenticated ingestion and a separately controlled checkpoint custodian before claiming audit-grade integrity.

No emails, paid resources, merges, deployments, or live data writes were performed.
