# E195: Same-bucket cleanup and reopening in the place waste ledger

## Falsifiable defect

The place/area summary ledger previously selected only one report per 20-minute
wall-clock bucket. When an open mass report, a cleanup, and a new open report
occurred in the same bucket, the later lifecycle transitions disappeared. This
contradicted the hotspot lifecycle semantics introduced in E194.

Three deterministic synthetic regressions were added **before** the fix. Exact
test-only head `0f64b61` failed **3 tests, 12 passed**; Ruff passed:
[red CI #40043105073](https://github.com/stoicsatvik/utsavfootprint/actions/runs/40043105073).

- 100 kg open -> cleaned five minutes later: removed mass incorrectly 0 kg.
- 100 kg open -> cleaned -> 20 kg new waste in ten minutes: generated
  mass incorrectly 100 kg instead of 120 kg.
- cleaned -> 20 kg reopened five minutes later: generated mass incorrectly 0 kg.

## Minimal correction

Within each spatial track, the 20-minute deduplication key now includes a
lifecycle-phase counter. Every resolved/non-resolved status transition advances
the phase; repeated views within one phase/bucket still use the strongest
provenance and confidence as before. Ordering is deterministic by observation
time, ingestion time, then ID.

This preserves cleanup and reopening events without summing repeated views.

## Limits and next discriminating test

All cases are **synthetic accounting tests**, not proof of physical cleanup,
mass accuracy, or authenticity. Ingestion metadata and provenance are supplied
by the observation producer. No field data, production database, or live
sensors were accessed. Cleanup status is not cryptographically authenticated.
A next security-focused experiment should test whether a low-trust producer
can forge a closure and suppress unresolved exposure. Do not treat the
reported removal mass as a weighed physical removal without independent
provenance.

This change is stacked on E194 PR #17. It is a draft integration candidate,
not a merge or deployment.
