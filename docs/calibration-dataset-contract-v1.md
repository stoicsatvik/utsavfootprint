# Calibration Dataset Contract v1

Status: frozen schema contract. This document defines admissibility and split rules; it does not contain or imply field observations.

## Purpose

Provide a reproducible boundary for evaluating Utsav Footprint source claims against later independently traceable measured or verified-official references without tuning on evaluation outcomes.

## Required record fields

Each record MUST contain:

- `dataset_version`: exactly `1`
- `pair_id`: stable unique identifier for the claim/reference pair
- `claim_id`: stable observation identifier
- `claim_source_id`: stable source identifier
- `claim_provenance`: one of `observed` or `modelled`
- `claim_observed_at`: timezone-aware ISO-8601 timestamp
- `claim_lat`, `claim_lon`: coordinates as recorded by the source
- `claim_confidence`: frozen value in `[0,1]`
- `reference_id`: stable later observation identifier
- `reference_external_ref`: independently traceable source reference
- `reference_provenance`: one of `measured` or `verified_official`
- `reference_observed_at`: timezone-aware ISO-8601 timestamp, not earlier than the claim
- `reference_lat`, `reference_lon`: coordinates as recorded by the reference source
- `split`: `development` or `evaluation`
- `inclusion_reason`: short rule-based explanation

Mass fields MAY be absent. If mass is evaluated, both claim and reference must preserve their original low/high bounds and units without retrospective conversion beyond a documented deterministic unit transform.

## Inclusion rules

A pair is admissible only when the reference is independently traceable, is measured or verified-official, does not predate the claim, and can be associated with the same physical event/location under a preregistered matching rule. Duplicate claims remain valid error observations but do not create independent-source confirmation.

## Exclusion rules

Exclude demo/synthetic observations, references without an external trace, model output used as its own reference, records with ambiguous event identity, and any record edited after its split outcome was inspected. Exclusions must be logged with pair ID and reason; deletion to improve metrics is forbidden.

## Deterministic split

Before outcomes are inspected, assign each physical event group to exactly one split using SHA-256 of `dataset_version + ':' + event_group_id`. Interpret the first 8 hexadecimal digits as an unsigned integer. Values modulo 5 equal to 0 are `evaluation`; all others are `development`. All claims and references for the same physical event group inherit the same split. This prevents near-duplicate event leakage.

## Freeze and identity

Serialize accepted records as UTF-8 JSON Lines with keys sorted lexicographically and one record per line. Sort records by `pair_id`. The dataset identity is SHA-256 of the exact serialized bytes. Record the hash, record count, creation timestamp, schema version, and source manifest in a sibling manifest before evaluation.

## Evaluation boundary

Development records may be used to debug software and preregister candidate weighting changes. Evaluation records must not be used to select thresholds, weights, matching rules, or features. Run the already-frozen calibration evaluator against evaluation records only after candidate logic is frozen.

Report pair count, independent source count, empirical accuracy, Brier score, and mass-midpoint RMSE when mass bounds exist. Report exclusions and missing mass explicitly. Do not convert these metrics into claims about cleanup impact or city-wide coverage.

## Promotion rule

Real-world calibration remains NOT YET PROVEN until a dataset satisfying this contract exists with a recorded manifest/hash, traceable references, frozen evaluator code, and reproducible metrics. Product or behavior-change impact requires separate intervention evidence.
