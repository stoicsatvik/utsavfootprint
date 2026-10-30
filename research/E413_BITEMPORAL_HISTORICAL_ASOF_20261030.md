# E413 | Historical as-of snapshots must respect ingestion time

**30 October 2026. Synthetic software audit, not a real-world cleanup claim.**

## Falsifiable question

Does an as-of snapshot at 08:00 incorrectly incorporate a cleanup that was
observed at 06:00 but only ingested at 10:00?

The inherited E411 `build_hotspots` checks observation event time but not
ingestion time. A late-arriving, declared-measured closure can therefore
retroactively close a historical snapshot. This is **hindsight leakage**:
knowledge acquired after the cutoff appears to have existed before it.

## Reproduction and correction

Synthetic open report: observed 04:00, ingested 05:00.
Synthetic declared-measured cleanup: observed 06:00, ingested 10:00.
Historical cutoff: 08:00 UTC.

- The existing `build_hotspots([...], 08:00)` includes both and reports
  `cleaned, 0h`. This is retained as a characterization of live semantics.
- The new opt-in `build_hotspots_as_of([...], 08:00)` includes only records
  with **both** `observed_at <= as_of` and `ingested_at <= as_of`, yielding
  `open, 4h`.
- The historical helper also excludes an event timestamp even one minute
  after the cutoff, despite E411's live five-minute clock-skew allowance.
- It delegates the unchanged 72-hour retention window, fusion, clustering,
  source deduplication and declared-provenance rules to `build_hotspots`.

Five deterministic contracts cover backfilled closure, future event time,
on-time closure, future-ingested-only data/immutability, and inclusive cutoff
plus the 72-hour lookback.

## Safety and limitations

This is a **new opt-in history helper**, not a silent change to live hotspot
behavior. Existing API consumers are not switched to the helper. The two
timestamp fields must represent trustworthy event and ingestion clocks;
a client-controlled `ingested_at` cannot establish a secure historical record.
Immutable append-only records are assumed. In-place edits/deletions and
late corrections require a separate revision/event log. Declared measured
provenance is not independently authenticated.

Exact repository pytest, Ruff, full inherited tests and GitHub Actions CI:
**not executed** pending a no-charge Actions budget check. No live database,
deployment or external communication was modified.

## Next falsifiable gate

Add append-only revision and correction events with server-issued ingestion
timestamps. Freeze a bitemporal synthetic fixture containing backfills,
clock-skew, edits and deletions. Compare the reconstructed state at each
cutoff with an independent event-log oracle; report false early closures,
late-detection latency and performance. Integrate this helper into historical
API queries only after exact-head tests and semantics review.
