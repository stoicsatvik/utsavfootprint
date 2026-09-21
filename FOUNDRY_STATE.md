# FOUNDRY_STATE

## Classification
- Tier: A / primary
- Claim state: SUPPORTED for the deterministic software pipeline and source-calibration ledger on committed fixtures; NOT YET PROVEN for real-world festival waste quantities, coverage, accuracy, calibration, or impact.
- Safety boundary: software sensing and evidence fusion only. Never bypass camera authentication or authorization; never relabel model output as measurement; never fabricate field observations.

## Current evidence
- Main head audited: `2a41d1937a0e8f081e22dc9be0febb870091fe31`.
- Source-calibration implementation head validated: `558511752d38a17856c5487a3280d1f28632d6f5`.
- Exact-head GitHub Actions run `35412743384` completed successfully: install `.[dev]`, `ruff check src tests scripts`, and `pytest -q` all passed on Python 3.12.
- Implemented primitives include observation ingestion/streaming, geospatial-temporal hotspot clustering, freshness/confidence decay, provenance classes, mass-range fusion, material-probability fusion, unresolved-waste-hours, authorized CCTV candidate generation, STAC scene discovery, official JSON/CSV ingestion, place waste summary queries, and deterministic claim/reference calibration metrics.
- Calibration fixtures prove measured/verified-official references must be later and traceable, repeated claims from one source cannot manufacture independent-source count, and evaluation reports empirical accuracy/Brier/mass-midpoint RMSE without mutating claims or fusion weights.

## Evidence boundaries
- `verified_official`, `measured`, `observed`, and `modelled` are provenance classes, not interchangeable truth labels.
- A CCTV persistent-change candidate is not automatically waste and does not establish mass.
- Satellite imagery discovery is not waste detection.
- Numeric confidence is not real-world accuracy merely because the calibration machinery itself is validated.
- Demo/synthetic observations never count as field data.

## Blockers
- No committed, independently verifiable real-world observation/reference set establishes waste mass, hotspot accuracy, or empirical calibration for Talao Pali, Thane, or any other festival site.
- No evidence yet establishes downstream cleanup or behavior-change impact.

## Highest-EV next action
Freeze a versioned real-world calibration dataset contract before ingesting any field observations: require traceable reference IDs, source/provenance/time/location identity, dataset version/hash, explicit inclusion/exclusion rules, and deterministic train/evaluation separation. Do not tune provenance weights until independently verifiable reference observations exist.

## Promotion gate
Promote real-world accuracy or calibration claims only after a versioned dataset with traceable references, frozen evaluation code, and reproducible metrics exists. Keep product impact claims NOT YET PROVEN until actual intervention evidence exists.
