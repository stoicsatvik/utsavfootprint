# E192: future timestamp outliers must not mask source health (2026-10-24)

## Problem and falsifiable contract

E188 correctly stopped future-dated `ingested_at` values from certifying a
source as `live`, but still selected the maximum timestamp within each
source. An otherwise healthy source with a valid report at T-2 minutes and a
single report at T+30 days was classified as `clock_skew`; a stale source
with a valid T-2 hours report and one T+6 minutes report was also classified
as `clock_skew`. Thus a single untrusted future timestamp could mask
otherwise usable source-health information.

**Hypothesis:** Choose the newest plausible ingestion timestamp (no more than
300 seconds ahead of server time) for the source's live/stale status; count
excluded future reports separately. If *all* reports are future-skewed,
preserve `clock_skew` as the source state. Do not discard or rewrite any
observation.

## Reproduction and implementation

Synthetic, frozen-clock tests in
`tests/test_source_health_outlier_resilience.py` cover:
- live report plus a 30-day-future outlier;
- stale report plus a six-minute-future outlier;
- two all-future reports, which must remain visibly `clock_skew`;
- the inclusive five-minute boundary and a clean-source control.

Test-first commit `f595c1e4` failed with **4 failed, 59 passed**, while Ruff
passed, on [Actions #40038028453](https://github.com/stoicsatvik/utsavfootprint/actions/runs/40038028453).
The first, second, and fourth cases selected the future report and returned
`clock_skew`; the third case exposed the missing anomaly count.

The correction in `SensorEngine.source_health` filters implausibly future
records **only for the health-recency selection**. The new additive
`SourceHealth.clock_skew_count` field reports excluded records. The original
`observation_count` includes all records, including future outliers.
When no plausible timestamp exists, `last_ingested_at` remains the latest
future timestamp and the state is `clock_skew`.

## Limits and next experiment

This is an engineering contract evaluated with synthetic records. No live
sensor, authenticated source, or historical database was examined. The
five-minute threshold is a policy choice, not a measured clock error bound.
`ingested_at` is currently producer-supplied and must **not** be presented
as trusted server receipt time. A malicious actor who controls `source_id`
could also inject a plausible *current* timestamp, falsely certifying that
source as live; this change does not address source authentication or that
larger trust-boundary problem.

A future experiment should add a separate server-generated `received_at`
audit field and compare producer timestamps against trusted receipt times,
without silently overwriting legacy evidence or claiming authentication.
Keep this change in a draft PR stacked on E188; no deployment, migration, or
main-branch merge is authorized.
