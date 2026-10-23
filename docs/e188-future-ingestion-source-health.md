# E188: future ingestion must not certify source health (2026-10-24)

## Falsifiable contract

A report whose `ingested_at` lies more than five minutes ahead of the server
clock must not make its source appear `live`. Previously,
`max(0, now - ingested_at)` clamped arbitrarily future timestamps to zero
seconds, so a source with a 30-day future timestamp was marked live.

The five-minute allowance matches the existing future-observation gating
policy in hotspot fusion. It is a **chosen engineering tolerance**, not an
empirically measured synchronization bound.

## Test-first negative evidence

Synthetic frozen-clock regression tests in
`tests/test_future_ingestion_source_health.py` cover 30-day future reports,
six-minute future reports, the five-minute boundary, and two-hour stale
reports. The pre-fix exact-head Actions
[#40024562097](https://github.com/stoicsatvik/utsavfootprint/actions/runs/40024562097)
reported **2 failed / 57 passed**: both future reports incorrectly
returned `live`; Ruff passed.

## Narrow correction and validation

`SensorEngine.source_health` now computes positive future skew explicitly:
over 300 seconds yields `clock_skew`; otherwise the existing live/stale
age classification remains unchanged. Negative ages remain reported as zero,
rather than inventing negative source ages.

The corrected exact-head Actions
[#40024606538](https://github.com/stoicsatvik/utsavfootprint/actions/runs/40024606538)
reported **59 passed** and Ruff success at `95a85078`.

## Boundaries and follow-up

Only synthetic observations were tested. No production source or database was
inspected. The result does **not** establish actual clock synchronization,
source authenticity, or correct ingestion provenance. Source health currently
selects the maximum `ingested_at` per source; one future-dated record can
therefore make the entire source `clock_skew` even if older valid reports
exist. That fail-visible behavior should be reviewed against operational
requirements before deployment. An independent next test should compare
server-stamped ingestion against producer-controlled timestamps and verify
that a malicious future report cannot suppress legitimate source visibility.

This change is intended as a draft, stacked on the unmerged E187 branch;
it does not change hotspot fusion or stored evidence and must not be merged
without review.
