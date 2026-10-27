# E324: Polar spherical-centroid falsification (27 October 2026)

## Concrete counterexample

Two valid synthetic observations at latitude **89.9995°**, longitudes **0°** and **180°**, are about **111.2 m** apart on the repository's spherical Haversine Earth model. They fit within the configured **120 m** clustering radius. The E314 arithmetic-latitude + circular-longitude method gives a centroid at **89.9995°** rather than the symmetric midpoint at the **North Pole (90°)**. That is an approximately **55.6 m positional error** in a synthetic scenario, not a field observation.

The circular longitude fix from E314 correctly handles the antimeridian but cannot solve high-latitude centroid geometry by itself. A weighted 3D unit-sphere resultant handles both geometries; for an undefined antipodal resultant the new implementation deterministically returns an actual input observation selected by stable ID. When evidence strengths are all zero, equal **positional** weights retain the location while fused confidence remains zero.

## Implemented and tested

- Both clustering centroid assignment and final hotspot fusion use the same unit-sphere geometry.
- Six new synthetic regression tests cover near-pole symmetry, three-point poleward shift, deterministic antipodal fallback, zero-confidence location, dateline/ordinary longitude and invalid weights.
- [Exact-head CI #40468191969](https://github.com/stoicsatvik/utsavfootprint/actions/runs/40468191969): **SUCCESS**, Ruff passed, **18 pytest tests passed** (new + inherited).
- Initial test-head CI #40468132162 failed only on unsorted test imports; the lint defect was corrected before the successful exact-head run. The earlier failure is retained in Actions history.

## Claim boundary and next experiment

**SUPPORTED IN TESTED SOFTWARE:** This synthetic polar geometry counterexample is corrected without regressing the tested dateline and zero-strength behavior.

**NOT YET PROVEN:** Ellipsoidal geodesic accuracy, physical waste truth, cluster stability for chain-shaped inputs, real sensor coordinates, or field performance. A spherical centroid is not an independent ground-truth geodetic measurement.

**Next:** Compare order/identity/time sensitivity of greedy clustering against an independently implemented geodesic complete-link or DBSCAN baseline on bounded synthetic adversarial shapes; preserve overmerging and oversplitting failures. Do not infer physical waste masses or source authenticity from geometric tests.

No deployment, field measurement, spending, outreach or main merge.
