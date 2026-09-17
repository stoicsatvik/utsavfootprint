# FOUNDRY_STATE

## Classification
- Tier: A / primary
- Claim state: SUPPORTED for the deterministic software pipeline on committed fixtures; NOT YET PROVEN for real-world festival waste quantities, coverage, accuracy, or impact.
- Safety boundary: software sensing and evidence fusion only. Never bypass camera authentication or authorization; never relabel model output as measurement; never fabricate field observations.

## Current evidence
- Main head audited: `2a41d1937a0e8f081e22dc9be0febb870091fe31`.
- GitHub Actions run `34625064370` completed successfully on that exact head.
- CI contract installs `.[dev]`, runs `ruff check src tests scripts`, then `pytest -q` on Python 3.12.
- Implemented primitives include observation ingestion/streaming, geospatial-temporal hotspot clustering, freshness/confidence decay, provenance classes, mass-range fusion, material-probability fusion, unresolved-waste-hours, authorized CCTV candidate generation, STAC scene discovery, official JSON/CSV ingestion, and place waste summary queries.

## Evidence boundaries
- `verified_official`, `measured`, `observed`, and `modelled` are provenance classes, not interchangeable truth labels.
- A CCTV persistent-change candidate is not automatically waste and does not establish mass.
- Satellite imagery discovery is not waste detection.
- Numeric confidence is not accuracy and must not be presented as calibrated unless calibration evidence exists.
- Demo/synthetic observations never count as field data.

## Blockers
- No committed, independently verifiable real-world observation set establishes waste mass or hotspot accuracy for Talao Pali, Thane, or any other festival site.
- No calibration ledger currently demonstrates empirical reliability by provenance class or source adapter.
- No evidence yet establishes downstream cleanup or behavior-change impact.

## Highest-EV next action
Build a deterministic source-reliability/calibration evaluation layer before expanding sensor breadth. It should compare source claims against later traceable reference observations, preserve source/provenance/time/location identifiers, report calibration/error metrics without silently changing base weights, and include synthetic fixtures that prove repeated/correlated reports cannot manufacture independent confirmation.

## Promotion gate
Promote real-world accuracy claims only after a versioned dataset with traceable references, frozen evaluation code, and reproducible metrics exists. Keep product impact claims NOT YET PROVEN until actual intervention evidence exists.
