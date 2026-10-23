# E176: read-only audit before timezone-contract integration

**Date:** 2026-10-23. **Status:** synthetic SQLite fixture validation; no
production database was accessed, modified, or migrated.

## Falsifiable risk

E175 rejects timezone-naive observation timestamps. The durable SQLite store
loads every saved JSON payload with `Observation.model_validate_json` during
`SensorEngine.start()`. One legacy payload with a naive `observed_at` or
`ingested_at` can therefore interrupt startup. A timestamp stored in the
indexed SQLite columns can also disagree with the timestamp inside its JSON
payload. Neither a producer's timezone nor the correct instant can be
reconstructed from a naive string alone.

## Red test and correction

Test-only commit `e8fc992` added five checks before the audit command existed.
[Red CI 39992974508](https://github.com/stoicsatvik/utsavfootprint/actions/runs/39992974508):
**5 failed, 40 passed**. The failures were caused by the absent audit script.
Implementation commit `4af1271` introduced the read-only audit; its
[CI 39993012079](https://github.com/stoicsatvik/utsavfootprint/actions/runs/39993012079)
failed at Ruff FURB162 before pytest ran. Commit `7ebae6a` removes the
unnecessary ISO `Z` substitution and closes the SQLite connection.

The tests create temporary SQLite databases and exercise aware offsets
representing the same instant, naive legacy timestamps, column/payload instant
disagreement, invalid JSON, and a missing database. The naive fixture also
demonstrates the E175 model rejects the stored payload.

## Operator audit

Run **against a backed-up, offline snapshot**, not an actively written
production database:

```bash
python scripts/audit_legacy_timestamps.py /path/to/snapshot.db
```

The command emits machine-readable JSON with counts, affected row IDs,
field names, and categorical issue codes, but never prints raw payloads.
Exit codes: **0** = clean; **2** = review required; **1** = missing/unreadable
database or schema. It checks both indexed SQLite timestamp columns and
the matching fields inside JSON payloads, including equivalence across
explicit UTC offsets. It uses a SQLite read-only connection, makes no
`UPDATE` or `DELETE`, and does not assume a timezone or quarantine records.

## Integration decision and limitations

**Keep E175 and E176 draft/unmerged pending operator review.** For every
flagged legacy row, establish the original producer timezone from independently
verifiable metadata. If provenance is unavailable, preserve the original row
and explicitly quarantine it in a separate reviewed migration plan rather
than relabeling the timestamp as UTC. Back up the database, log the mapping,
test restoration, and only then propose a separately reviewed migration.

A clean audit only proves the audited timestamp representations are parseable,
timezone-aware, and internally consistent. It does not validate clocks,
authenticity, all payload fields, historical accuracy, or production readiness.
SQLite WAL sidecar behavior is another reason to audit a snapshot.

**Next experiment:** run the audit on an authorized sanitized legacy snapshot,
quantify the fraction of affected rows by source and timestamp field, and
design a reversible, provenance-based migration/quarantine process.
