# E426 | Finite mass can overflow hotspot mass-hour metrics

**Date:** 2026-10-30. **Scope:** synthetic numeric counterexample and opt-in, unmerged output correction. No live observations, production database changes, or claims about real physical waste.

## Falsifiable question and negative result

E424 rejects non-finite input mass. Does that ensure finite mass and mass-hour outputs after fusion? **No.** Two independent inputs with finite `mass_kg_high=1e308` cause Python's original `statistics.median([1e308, 1e308])` to evaluate to positive infinity because the even-sample implementation adds the values. Even a single finite `1e308` mass multiplied by two unresolved hours yields positive infinity. Pydantic's permissive output fields can serialize those non-finite derived values as JSON `null`, obscuring why evidence disappeared. A standalone Python 3.11+ reproduction confirmed both numeric failures and strict JSON rejection of the result. This is not a field-data observation.

## Explicit output contract

- For nonnegative finite mass candidates, compute the even-sample median as `lower + (upper - lower) / 2`, avoiding overflow in the intermediate sum.
- Preserve original finite fused `mass_kg_low` and `mass_kg_high` values.
- Compute each derived mass-hour metric; if multiplication overflows, return `null` **with** `unresolved_waste_hours_overflow=true`. A missing mass instead returns `null` with the flag **false**. If one bound overflows, the other finite bound is preserved.
- Constrain derived output metrics and unresolved hours to finite nonnegative values at model validation. No arbitrary physical mass cap or saturation value is invented.
- Preserve zero-duration closure: even enormous finite mass multiplied by zero produces zero, not overflow.
- The existing `/metrics` consumer previously used `or 0`, so it silently undercounted flagged nulls. Prometheus now emits `NaN` for an affected aggregate and reports `utsav_unresolved_waste_hours_overflow_hotspots`. A sum of individually finite values that itself overflows is also emitted as `NaN`.

## Tests

`tests/test_e426_finite_waste_hour_metrics.py` includes frozen-time regression tests for single-source overflow, two-source even median, zero-duration cleanup, ordinary finite metrics, missing mass, JSON serialization, schema rejection of injected non-finite derived output, and the Prometheus consumer's flagged-null and aggregate-overflow behavior.

**Validation status at initial commit:** Standalone numeric reproduction passed. Exact repository pytest, Ruff, and CI have not yet been verified; do not equate a local numeric demonstration with integration success. The branch is stacked on E424 and remains draft/unmerged.

## Remaining limitations

The overflow flag is a numerical diagnostic, not a physical plausibility judgment or measurement-quality score. Downstream consumers must interpret flagged `null` as unrepresentable, not as zero waste. Extremely large *finite* mass can still be implausible in the physical domain. Authenticated provenance, independently retained revision checkpoints, and policy for physically plausible mass intervals remain separate research gates.

## Next experiment

Test dashboard and downstream monitoring alert rules with flagged-overflow fixtures, including mixed missing and overflowed mass bounds. The current aggregate policy conservatively emits `NaN` for a missing bound whenever the hotspot-level overflow flag is set; a future per-bound flag could avoid this loss of precision.