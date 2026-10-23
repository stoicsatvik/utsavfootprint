# E187: finite mass-claim boundary (2026-10-24)

## Falsifiable defect

The existing Observation model constrained mass estimates with `ge=0`, but
Pydantic permits positive infinity under that constraint. For a finite lower
bound and `mass_kg_high=Infinity`, the interval-order check also passes.
The legacy read-only SQLite audit then reports the row as clean, while hotspot
fusion can propagate an infinite mass or unresolved-waste-hour estimate.

This is an input-validation problem, **not** evidence of an actual bad sensor
record or a calibrated real-world mass estimate.

## Preserved test-first evidence

- Synthetic regression-only commit `459eb5e8`: [red Actions
  #40017085692](https://github.com/stoicsatvik/utsavfootprint/actions/runs/40017085692).
  Ruff passed; **2 failed, 53 passed**. The high-bound infinity was accepted
  by the Observation model and the read-only audit returned exit 0. The low-bound
  infinity case was already rejected by the existing low > high interval check.
- Correction commit `a1518cf4`: add `allow_inf_nan=False` to the two
  optional mass-bound fields. Preserve nonnegative and interval-order rules.
  [Green Actions #40017213738](https://github.com/stoicsatvik/utsavfootprint/actions/runs/40017213738):
  Ruff passed, **55/55 pytest tests passed**.
- New tests cover both mass bounds in Python and JSON validation, a synthetic
  SQLite audit that leaves its database byte-for-byte unchanged, and a finite
  [100, 200] kg fusion control.

## Safety and remaining uncertainty

No real database, external sensor, or production deployment was accessed.
The audit reports `invalid_observation` for invalid stored mass claims; it
does not rewrite, delete, or guess their values. The existing timestamp,
provenance, and identity constraints are unchanged. The patch is stacked on
draft PR #13 and must not be merged without review.

Next step: run the read-only audit on an authorized offline legacy snapshot
and classify any incompatible records before designing a reversible migration.
Do not silently coerce Infinity to zero or another plausible mass estimate.
