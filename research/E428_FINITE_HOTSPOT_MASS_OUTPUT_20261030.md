# E428 | Validate finite, ordered fused mass intervals at output boundary

**Date:** 2026-10-30. **Scope:** validation contract for `HotspotState`, stacked on E427 draft PR #43. No real-world mass estimates, production changes, or external communication.

## Falsifiable failure

E423 and E424 constrain non-finite probabilities and input observation mass; E426 and E427 constrain derived mass-hour metrics. However, the fused output model still declared `mass_kg_low` and `mass_kg_high` as unconstrained optional floats. A direct `HotspotState.model_validate` could accept `NaN`, `+Infinity`, `-Infinity`, negative mass, or a lower mass bound greater than its upper bound. This creates a bypass for callers, cached states or future adapters that do not construct output exclusively through current fusion.

**Negative reproduction:** A local Pydantic 2.13.5 source-equivalent old-model check accepted `(+Infinity, +Infinity)` and `(NaN, 10.0)` and serialized the non-finite values to JSON `null`. It also accepted a negative low bound. These are serialization/invariant defects, **not** observed waste measurements.

## Minimal correction

- Add `Field(ge=0, allow_inf_nan=False)` to both optional fused mass bounds.
- Reject an inverted interval when both mass bounds are present.
- Preserve partial/missing intervals, valid zero and large finite mass values. No invented physical plausibility cap or material-sum normalization.
- Add `tests/test_e428_finite_hotspot_mass_output.py` with 14 parametrized cases for invalid values, inverted intervals, and finite/missing JSON round trips.

## Validation and limits

- Source-equivalent isolated Pydantic 2.13.5/pytest 9.0.2 mirror: **14/14 passed**. The mirror duplicates the output model's relevant fields and validator. It is **not** an exact-repository test.
- Full repository pytest, Ruff, GitHub Actions and integration checks: **NOT RUN**. GitHub billing notice on 2026-10-29 reported all 2,000 included Actions minutes consumed; writes use `[skip ci]` to avoid unverified billable workflows.
- GitHub-hosted branch changes are unmerged and unreviewed. Current fusion normally emits finite, ordered bounds, so the issue is a **model-boundary defense**, not proof that current normal ingestion emitted invalid mass.

## Next experiment

After a verified no-charge runner or the 2026-11-01 included-minute reset, run exact-head pytest/Ruff and test that historical replay, JSON and API responses reject non-finite fused mass without erasing legitimate missing bounds. Review the entire E413-E428 stack before merging. Independent evidence custody and physical verification remain separate unsolved requirements.
