# E424 | Positive-infinite mass bounds survive nonnegative validation

**Date:** 2026-10-30. **Scope:** synthetic ingestion counterexample and bounded Pydantic input correction. No live observations or deployments.

## Falsifiable question

Does `Observation.mass_kg_low` / `mass_kg_high` reject all non-finite inputs, given that both fields currently use `Field(ge=0)`?

**No.** Pydantic v2.13.5 accepts positive infinity for a nonnegative float field, including coerced `"Infinity"`. `model_dump_json()` renders the accepted value as `null`. In the existing `_fuse_mass` path, a sole source with `mass_kg_high=+inf` produces a non-finite fused upper bound; multiplying it by unresolved hours can contaminate metrics. This is a deterministic input/serialization defect, **not evidence of a real malicious report or measured physical mass**.

## Reproduction and negative result

A source-equivalent local Pydantic v2.13.5 model with `mass_kg_high: float | None = Field(default=None, ge=0)` accepted `math.inf` and produced `{"low":null,"high":null}` in the minimal two-field reproduction. This shows the original predicate was insufficient. The original implementation was not modified to hide this result.

## Correction

Add `allow_inf_nan=False` to both Observation mass interval fields, retaining `ge=0`, optional missing bounds, and the existing `mass_kg_low <= mass_kg_high` invariant. The change is intentionally limited to the input model; it does not impose new physical mass caps or alter the fusion estimator.

New `tests/test_e424_nonfinite_mass_intervals.py` covers both fields with `+inf` and string `"Infinity"`, preserved rejection of NaN/negative values, and finite/missing control cases including downstream fusion.

## Validation and limitations

- Source-equivalent local Pydantic 2.13.5 checks: **passed** (the original `+inf` acceptance was reproduced; 10 corrected invalid combinations rejected; finite/missing controls accepted).
- **Exact repository pytest, Ruff and CI are not yet confirmed** at the time of this report. Do not substitute the isolated model reproduction for full integration tests.
- Very large but finite inputs can still overflow in downstream `mass * unresolved_hours`; fixing this requires an explicit domain policy or a separately tested overflow-safe derived metric. This correction does not authenticate source identity, cleanup, or mass measurements.
- No merge, live database mutation, external communication, or manually triggered paid CI.

## Next falsifiable experiment

Construct a finite-only input that overflows `unresolved_waste_hours_high`, then specify a bounded/flagged output contract that preserves evidence instead of silently converting infinity to JSON null. Independently review the E413-E424 stacked branch series before any merge.
