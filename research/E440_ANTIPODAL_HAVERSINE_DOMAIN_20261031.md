# E440 | Near-antipodal Haversine binary64 domain failure (31 October 2026)

## Falsification
On the unmerged E429/E430 research branch, `haversine_m` used
`2*R*asin(sqrt(q))` without guarding the mathematical domain `0 <= q <= 1`.
For valid latitude/longitude inputs, binary64 evaluation of the standard
Haversine expression can yield `q = 1.0000000000000004` near antipodes.
The square root remains greater than one and Python `math.asin` raises
`ValueError: math domain error`.

Frozen reproducer, degrees:
`(61.13111980259248, -103.81561493387612, -61.13111979418826, 76.1843851189758)`.
The pair is almost antipodal, with both coordinates inside the validated
latitude/longitude domain. This is a deterministic synthetic numeric case,
not a field measurement. The same helper is called by greedy clustering,
so one such pair can abort clustering even though they should be separate.

## Correction and negative controls
Clamp the dimensionless Haversine intermediate to `[0, 1]` immediately
before `sqrt/asin`. Do not alter the physical radius, clustering threshold,
temporal logic, provenance weighting, or output schema.

Five regression tests were committed: explicit former-domain-error
reproduction, two distant observations remaining in separate clusters,
zero/dateline distances, equatorial one-degree distance, and 10,000
deterministic valid random pairs checked for boundedness and symmetry.

## Validation scope
A standalone Python 3 exact-expression local mirror of the patched
Haversine function passed 5/5 tests, including the frozen overshoot,
10,000 random pairs and near-antipodal perturbations. The unclamped
expression was independently executed and raised ValueError for the
frozen pair. The **committed repository tests and full inherited suite
have NOT been run**. No GitHub Actions rerun was requested because
prior branch notes report exhausted included Actions minutes.

## Claim fence
- **REJECTED:** unguarded `asin(sqrt(q))` is defined for all validated
  geographic coordinates under binary64 arithmetic.
- **SUPPORTED IN STANDALONE NUMERIC MIRROR:** clamping prevents this
  narrow domain failure without changing ordinary tested distances.
- **NOT YET VERIFIED:** exact repository integration, complete geospatial
  correctness, field hotspot identity, real-world waste outcomes.

Next: run the committed regression plus full pytest/Ruff in confirmed
no-charge capacity, and compare with existing E314/E324 geospatial tests.
Do not merge/deploy without integration review.
