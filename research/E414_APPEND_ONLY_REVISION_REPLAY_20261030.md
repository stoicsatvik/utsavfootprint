# E414 | Append-only revision replay is required for trustworthy historical views

**30 October 2026. Synthetic software integrity experiment; no field cleanup claims.**

## Source-inspected falsification

E413 added `build_hotspots_as_of`, correctly requiring observation and ingestion
timestamps at or before a historical cutoff **if the supplied records are immutable
and complete**. However, `SQLiteObservationStore._upsert_sync` uses
`ON CONFLICT(id) DO UPDATE SET observed_at, ingested_at, payload`. A correction
or deletion of a record can erase the prior payload, so an old cutoff cannot be
reconstructed from the current SQLite table alone.

An independent in-memory SQLite reproduction using the store's exact SQL
upsert shape inserted `site=open` then `site=cleaned` under the same ID.
The table retained only `site=cleaned`. This proves the information-loss
property of that SQL pattern; it is **not** an exact repository integration run.

## Bounded implementation

`src/utsav_sensor/history.py` adds an **opt-in, in-memory** revision replay
helper and historical hotspot wrapper. Revision records contain a positive,
contiguous server-sequence number, receipt timestamp, observation ID and either
a full observation or a deletion tombstone. The replay:

- Applies only revisions received at or before the requested cutoff.
- Replays corrections and deletions without changing the live SQLite store.
- Resolves equal receipt times by sequence and returns defensive observation copies.
- Rejects duplicate/missing-prefix/gapped sequences, nonchronological receipt
  times, naive timestamps, mismatched IDs and future ingestion relative to receipt.
- Reuses E413's strict `build_hotspots_as_of` for fusion after replay.

**Important limitation:** contiguous sequence checks can catch missing prefixes
and interior gaps, but cannot detect a missing final suffix without a trusted
head sequence or signed checkpoint. The helper requires an independently
retained complete revision stream. The current SQLite store **does not
produce or retain that stream**. A caller-supplied `recorded_at` or
`sequence` is not authenticated. Do not use this helper as an audit trail
or expose historical claims in production until server-issued receipts and
durable append-only persistence exist.

## Executed validation

- Five isolated Python/Pydantic local mirror tests passed, covering late
  corrections, tombstones, equal-time ordering, malformed logs and defensive
  copies. Additional negative cases for missing sequence prefixes and gaps
  were included in the malformed-log test.
- Local Python compileall passed.
- In-memory SQLite source-SQL characterization confirmed overwrite loss.
- Exact repository pytest, Ruff, live store integration, and exact-head CI
  **were not executed**. GitHub's 29 October billing alert reported
  2,000/2,000 included Actions minutes consumed; commits use `[skip ci]`.

## Next falsifiable gate

Implement a separate append-only SQLite revision table with server-assigned
sequence and receipt time, without backfilling invented historical receipts.
Freeze a dataset with original observations, corrections, tombstones, ties,
late arrivals and an intentionally missing suffix. Compare historical states
against an independently generated event-log oracle and require a trusted
checkpoint to detect incomplete tails. Run exact-head repository tests and
migration tests before any live ingestion or API integration.

No existing database was modified, no deployment or merge was made, and no
email or external commitment was sent.
