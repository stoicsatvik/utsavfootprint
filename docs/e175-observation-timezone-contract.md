# E175: explicit observation timestamp contract

**Date:** 2026-10-23. **Scope:** synthetic timestamp validation in the Utsav Footprint software API and sensor model. No field-clock calibration.

## Falsifiable defect

The original Pydantic `Observation` model accepted timezone-naive
`observed_at` and `ingested_at` values. Fusion uses an aware UTC `now`,
so subtracting a naive observation timestamp raises `TypeError` and can
interrupt the hotspot endpoint or an ingestion-triggered update. Aware
timestamps with an explicit non-UTC offset represented correct instants,
but retained inconsistent timezone representations across records.

**Test-only commit:** `b75d67e77a858f4d348332076b3796697c8012f2`.
[GitHub Actions PR CI 39983818845](https://github.com/stoicsatvik/utsavfootprint/actions/runs/39983818845)
**FAILED as expected**: Ruff passed, **3 failed / 37 passed**. The failures
proved that both naive fields were accepted and non-UTC offsets were not
canonicalized. The equivalent-instant hotspot comparison already passed.

## Minimal intervention

At the `Observation` model boundary, both timestamps must contain a
usable UTC offset. Naive timestamps are rejected with a Pydantic validation
error rather than guessing the producer's timezone. Aware timestamps are
normalized to UTC before fusion or storage. Default-generated timestamps
already use UTC and are unchanged. This does **not** change the E174
five-minute future-clock-skew policy or the 72-hour historical window.

Four regression tests cover rejection of naive observation and ingestion
timestamps, conversion of a +05:30 offset to UTC, and equal fusion results
for equivalent instants in different offsets.

## Safety and limitations

This is an explicit **API contract tightening**. Old clients sending naive
timestamps will receive validation errors (HTTP 422 at the FastAPI model
boundary). Existing persisted records with naive timestamp strings can
also fail to load on restart. **Do not merge or deploy without auditing
legacy SQLite data and arranging an explicit producer-timezone migration
policy.** Do not silently relabel old naive wall times as UTC.

The correction does not authenticate producer clocks, calibrate actual
clock skew, prevent deliberate timestamp spoofing, or establish real-world
sensor accuracy. It only removes timezone ambiguity for newly validated
observations. Satellite search request timestamps are outside this
experiment's scope.

## Next experiment

Before integration, test stored-record compatibility with a legacy
naive-timestamp fixture and choose an auditable migration/quarantine path.
Then measure real producer offset distributions before modifying the
five-minute tolerance.
