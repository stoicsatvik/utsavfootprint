# E423 | Non-finite material evidence must fail validation

**30 October 2026. Synthetic input-validation counterexample. No live data or deployment.**

## Falsifiable question

Can an observation pass `Observation.material_probs` with a non-finite material fraction, and subsequently serialize that fraction as JSON `null` rather than a numeric probability?

**Yes, before this correction.** The prior predicate `v < 0 or v > 1` accepts `float("nan")` because both comparisons are false. Pydantic v2 accepts NaN in `dict[str, float]` unless separately constrained; `model_dump_json()` emits `null` for it. A source-equivalent local Pydantic 2.13.5 experiment reproduced acceptance and JSON null output. This is not evidence of malicious live ingestion.

## Bounded correction

Use `math.isfinite(v)` before checking the [0, 1] range in `Observation.material_probs`. This rejects NaN and infinities (including string `"NaN"` coerced by Pydantic) before fusion. It preserves valid finite boundary values 0, 0.5 and 1. The correction is limited to the existing material probability validator. It does not change historical receipts, provenance authentication, schema, persistence, or other numeric fields.

## Regression contract

`tests/test_e423_nonfinite_material_probabilities.py` asserts rejection of NaN, both infinities, out-of-range finite values, and coerced NaN text. It asserts that valid finite boundary inputs still serialize and fuse. All cases use synthetic observations.

## Validation

- Original predicate: source-equivalent Pydantic 2.13.5 reproduction accepted NaN and serialized it as JSON null (**negative result**).
- Corrected predicate: source-equivalent Pydantic 2.13.5 checks rejected all six invalid inputs; valid boundary JSON remained numeric.
- Exact repository pytest, Ruff, and GitHub Actions CI: **not yet confirmed** for this branch. E421's earlier 68-pass result does not validate E423.

## Remaining limitations and next gate

A `materials` dict still represents individually bounded fractions, not necessarily a normalized probability distribution: the sum can exceed 1, and semantics of co-occurring materials are not established. Other free-form `metadata` values are not covered. Run exact-head CI, inspect the test output, and separately decide whether material values are independent probabilities or mutually exclusive shares before adding a sum-to-one invariant. No physical-cleanup verification claim.
