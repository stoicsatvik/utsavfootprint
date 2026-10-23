# E177: full-payload integrity gate for legacy SQLite snapshots

**Date:** 2026-10-23. **Status:** synthetic-fixture validation; no production database accessed.

## Falsifiable failure

E176 checked timestamp parseability and column/payload instant consistency, but a
legacy row with fully valid UTC timestamps and an invalid observation schema
(for example, latitude 999) could pass the audit with exit code 0. The actual
`SQLiteObservationStore._all_sync()` then rejects the same payload through
`Observation.model_validate_json` and can interrupt startup.

A different silent integrity risk arises if the JSON payload's `id` disagrees
with the SQLite primary key, or is missing: Pydantic's default ID factory
can supply a new ID on load.

## Change and tests

The read-only audit now checks each parseable JSON object against the current
`Observation` schema, with categorical `invalid_observation` findings.
Timestamp-specific failures keep their existing codes rather than acquiring
duplicate schema findings. It separately flags `missing_id` and
`id_mismatch`, including when the model would otherwise generate a default.

The new regression tests use synthetic SQLite rows with valid UTC timestamps
but (1) invalid latitude, (2) conflicting IDs, and (3) missing payload ID.
They assert nonzero review status, specific issue codes, and byte-for-byte
unchanged database files. The invalid-latitude case also reproduces failure
of the production model loader.

## Operator use and safety

Run on an **authorized, backed-up, offline snapshot** after installing the
project dependencies:

```bash
pip install -e .
python scripts/audit_legacy_timestamps.py /path/to/offline-snapshot.db
```

Exit 0 means the audited records satisfy the **current** model contract,
timestamp consistency, and row identity. Exit 2 means manual review; exit 1
means the database could not be inspected. The audit does not infer timezones,
repair IDs, mutate records, delete evidence, or expose raw payload values.

## Integration gate and remaining uncertainty

Keep this change **draft and unmerged**, stacked on E176. A valid audit
is not evidence of sensor calibration, source authenticity, historical truth,
or migration safety. The tool currently reports row IDs and issue codes; treat
reports as sensitive operational metadata. It does not validate external
references or resolve source provenance. An old schema may legitimately
differ from the current one; all such findings require human review, not
automatic repair.

**Next experiment:** evaluate an authorized sanitized legacy snapshot and
quantify the prevalence of schema and ID integrity defects. Before any
migration, establish provenance, make a backup, and prove rollback on a copy.


## 2026-10-24 addendum: non-finite material-probability claim

**Reproduced failure:** the model's former `v < 0 or v > 1` range check
accepted `float("nan")` because neither comparison is true. Pydantic also
accepted the corresponding `NaN` JSON token, despite its non-standard JSON
representation. This could pass the E177 legacy audit with exit 0 and then
propagate a non-finite material estimate into hotspot output, where strict
JSON serialization may fail.

**Test-first evidence:** CI run
https://github.com/stoicsatvik/utsavfootprint/actions/runs/40008958789
on commit `ee508e9` had **2 expected regression failures and 49 passes**:
the model did not reject NaN and the read-only audit returned exit 0.
Earlier intermediate CI runs exposed test import/formatting problems, which
were corrected before interpreting the model-level failure.

**Narrow correction:** material probabilities must be finite as well as in
[0, 1]. Existing valid finite values retain their behavior. The existing
read-only legacy audit now flags this case through its current
`invalid_observation` code, without rewriting the snapshot.

**Validation:** exact-head CI run
https://github.com/stoicsatvik/utsavfootprint/actions/runs/40009057690
on commit `fbb73bd` passed Ruff and **51/51 pytest tests**.
The three added tests cover Python/JSON model rejection, an unchanged
synthetic SQLite snapshot, and a valid finite-value fusion control.

**Boundary:** This is synthetic validation only. It does not prove that any
real stored record contains NaN or establish a safe migration policy. Do not
automatically coerce non-finite claims to zero, and do not merge until the
stack and any authorized legacy snapshot have been reviewed.
