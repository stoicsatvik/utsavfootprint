# E314 | Dateline and zero-strength hotspot geometry

Date: 27 October 2026. Deterministic synthetic geometry only. No real environmental measurements.

## Falsification

The existing clustering algorithm uses arithmetic longitude means. Two reports at +179.9998 and -179.9998 degrees are approximately 44.48 m apart at the equator, but their arithmetic midpoint is 0 degrees. A third report at +179.9997 degrees is approximately 33.36 m from their correct circular midpoint yet approximately 20,015 km from the arithmetic midpoint. The 120 m greedy cluster therefore splits one physically adjacent group. The fused hotspot longitude is likewise wrong.

A separate zero-strength counterexample has one observation at (19.076, 72.8777) with confidence 0. The previous weighted position calculation divides a zero numerator by a fallback denominator of 1, reporting (0, 0), despite the observation having a known location. This incorrectly conflates low evidentiary confidence with unknown coordinates.

## Correction and acceptance

- Use circular longitude means in cluster selection and hotspot fusion.
- If all strength weights are zero, use equal weights **for position only**; fused evidentiary confidence remains zero.
- Preserve normal nearby-longitude behavior.
- Four deterministic tests exercise both negative cases and ordinary geometry.

## Boundaries

SUPPORTED for these synthetic geometry counterexamples only. This is not validation of satellite/CCTV waste detections, physical cleanup, geodetic centroid accuracy near poles, or a production multi-worker consistency guarantee. Greedy clustering can still be order-dependent for other geometric arrangements. Future work: test high-latitude geodesic centers, permutation stability and adversarial chain-shaped clusters against an independent geospatial baseline.
