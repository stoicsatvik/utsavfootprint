# E427 | Per-bound overflow provenance in mass-hour monitoring

**Date:** 2026-10-30. **Scope:** synthetic counterexample and opt-in, unmerged monitoring correction. No real waste measurements or production deployments.

## Falsified interpretation

E426 correctly prevented finite mass inputs from producing unmarked infinite derived metrics, but its single hotspot-level `unresolved_waste_hours_overflow` boolean was insufficient to determine which bound failed. In a partial-bound synthetic state with missing low mass and overflowed high mass, the original `/metrics` code returned `NaN` for **both** totals. The low total should retain the existing skip-missing policy, not be classified as overflow. This is a numerical/monitoring defect, not evidence of a physical event.

## Bounded correction

- Emit `unresolved_waste_hours_overflow_low` and `unresolved_waste_hours_overflow_high` separately from fusion while retaining the existing aggregate boolean.
- Represent absent per-bound flags as `null` only for legacy state compatibility. Explicit new states always carry booleans.
- `/metrics` now treats a missing bound as overflow only when that bound is explicitly flagged. If its per-bound flag is absent (`null`), the old aggregate flag conservatively marks it `NaN`; no unsupported precision is inferred.
- Reject contradictory flags in model validation, including an overflow flag attached to a finite metric.
- Preserve E426's existing aggregate-overflow detection and hotspot-level overflow count. No physical plausibility cap is invented.

## Reproduction and validation

The original aggregate-only behavior was reproduced in a local Python 3.13.5/Pydantic 2.13.5 source-equivalent mirror: missing low + overflowed high yielded low `NaN` instead of the existing skip-missing total. The proposed contract passed **9/9 isolated pytest checks** covering mixed bounds, legacy fallback, both-bound overflow, ordinary missing data, aggregate overflow, and inconsistent flags. These are not exact-repository integration tests.

New repository regressions are in `tests/test_e427_bound_overflow_precision.py`, covering fusion JSON, missing mass, mixed-bound Prometheus output, legacy fallback and invalid flags.

## CI/billing constraint

BuildWithSatvik received a GitHub billing notice on 2026-10-29 confirming **2,000/2,000 included Actions minutes used** and warning that further usage may be billed unless a $0 Actions budget is configured. The current repository workflow runs on both `push` and `pull_request`. To avoid initiating unverified paid CI, the E427 commit uses `[skip ci]`; full repository pytest/Ruff/Actions are **not** claimed to have passed. The next gate is exact-head tests after a verified no-charge runner is available or the included minutes reset on 2026-11-01.

## Remaining uncertainties

The current fusion requires both mass bounds for mass evidence, so the mixed missing/overflowed state is a deliberately synthetic downstream compatibility test, not a claim that the normal fusion path emits partial mass intervals. Skipping missing mass bounds in Prometheus remains a pre-existing policy, and dashboards/alert rules have not been validated. The entire stacked revision-ledger series remains draft and unmerged.
