# E174: Future-dated observation gating (synthetic software contract)

## Problem and falsifiable counterexample

Before E174, `build_hotspots` admitted every observation satisfying
`now - observed_at <= 72 hours`. The expression has no lower bound.
Consequently, an observation dated **30 days in the future** produced a
present-day hotspot, and a second source dated **six minutes ahead** inflated
the independent-source count of a current hotspot from 1 to 2.

These are **synthetic** observations, not real Mumbai sensor measurements.

## Intervention and scope

Only the active-hotspot filter changes. An observation is eligible when
`-5 minutes <= now - observed_at <= 72 hours` (inclusive). Five minutes
is a conservative **clock-skew policy assumption**, not a measured or
statistically calibrated clock-offset bound. Reports outside the window
remain in storage; the API ingestion contract, raw audit history,
source-fusion weights, and geospatial clustering are unchanged.

An observation more than five minutes in the future is deferred, rather
than being treated as independent evidence today. As time advances it
can become eligible without rewriting its original timestamp.

## Preserved negative and corrected evidence

- Test-only commit `adeb4ed371b78bee22ea172b0e5be8e4e92f4580`:
  [PR CI run 39976002018](https://github.com/stoicsatvik/utsavfootprint/actions/runs/39976002018)
  **FAILED as expected** with 4 failed, 32 passed. Ruff passed.
  The four failures demonstrate far-future contamination, independent-source
  inflation, the five-minute boundary, and seeded future offsets.
- Correction commit `1bfe1d0959b92b9393afe287b17c67badc16d21f`:
  [PR CI run 39976068647](https://github.com/stoicsatvik/utsavfootprint/actions/runs/39976068647)
  **SUCCESS**, Ruff passed, **36/36 pytest tests passed**.
- Additional coverage: exactly five minutes ahead is eligible, five minutes
  and one second ahead is deferred, the latter becomes eligible when time
  advances by one second, and the old inclusive 72-hour past boundary
  is preserved. A seeded loop checks 200 future offsets.

## Limitations and next falsifiable questions

This establishes only an active-state time-window contract. It does **not**
establish the true clock-offset distribution of field sources, authenticated
timestamps, resistance to adversarial time spoofing, timestamp-perturbation
invariance of greedy clustering, or optimality of the five-minute allowance.
Naive datetimes and timezone normalization remain separate input-validation
questions. The current `freshness` function clamps small negative ages to
zero, so tolerated near-future reports are scored as maximally fresh.

No destructive changes or merges. This is a draft stacked on E173 and
must be reviewed before integration.
