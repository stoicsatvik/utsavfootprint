# E349 | Observation-ID permutation sensitivity in conservative hotspot clustering

Date: 2026-10-28. All coordinates, times, and source labels in this test are synthetic. No observed waste piles, mass, privacy-sensitive imagery, field measurements, or accuracy claims.

## Falsification target

E336 guaranteed pairwise spatial diameter <=120 m and full time span <=24 h, but sorted simultaneous observations by arbitrary observation ID. With three reports at eastward offsets 0, 100, and 200 m, all six permutations of ID assignment preserve identical physical observations. Under the pre-E349 rule, three assignments yield the pair (0,100) and three yield (100,200); each partition satisfies the geometric bounds. Thus the IDs, not physical evidence, selected the inferred hotspot grouping.

## Correction and controls

The production greedy algorithm now sorts by timestamp, latitude and longitude unwrapped at the largest unoccupied circular gap; IDs break ties only when observations share the same physical ordering coordinates. This retains the E336 pairwise-distance/time-span checks, including the antimeridian, without switching the clustering contract or requiring a database migration. The regression enumerates all six renamings at both ordinary longitude and an antimeridian-crossing base, reverses ingestion order, and preserves the 0/100/200 alternative partition as an explicit ambiguity control. The existing 64 seeded invariant fixtures remain applicable.

**Scope:** ID-renaming invariance for physically distinct coordinate/time tuples is a software invariant, not an externally validated improvement in pile deduplication. The method remains greedy and may be sensitive to small coordinate/timestamp perturbations or the location of the circular seam when unrelated distant reports are added. Physically identical coordinates/timestamps with different IDs can still affect which identical observation is assigned to a group, although not its spatial signature. Canonical sorting does not solve the underlying physical identity problem.

## Reproduce

```sh
python -m pip install -e '.[dev]'
pytest -q tests/test_e336_cluster_linkage.py
ruff check src tests scripts
pytest -q
```

**Claim:** Pre-E349 ID-independent partitioning REJECTED by six exact synthetic permutations. Post-E349 ID-independent physical partitioning for the tested distinct-position fixtures is SUPPORTED IN TESTED SOFTWARE once CI passes. Real-world overmerge, oversplit, temporal continuity, and hotspot identity NOT YET PROVEN.

**Next:** Compare against order-invariant complete-link and density methods on authorized independently labeled duplicate/nonduplicate observations, measuring error, latency and hotspot-ID continuity. No deployment or main merge.


## Follow-on negative control: timestamp perturbation

A deterministic two-geometry regression now tests the same three physically fixed
observations at eastward offsets 0/100/200 m, both at ordinary longitude and across
the antimeridian. With simultaneous timestamps, greedy grouping pairs the 0 m and
100 m observations. Moving only the 0 m timestamp forward by one microsecond
and the 200 m timestamp backward by one microsecond reverses the processing
order and instead pairs the 100 m and 200 m observations. Spatial coordinates,
IDs, sources, evidence strengths, and the 120 m/24 h caps are unchanged.
Reversing input order does not repair the difference.

**Negative result:** ID-renaming invariance is not temporal-perturbation stability.
Even a 2-microsecond total observation-time spread can change the membership
of an ambiguous spatial chain. This is an algorithmic synthetic counterexample,
not a claim that a two-microsecond sensor error has been measured in the field.
The current implementation is deliberately unchanged: changing clustering
policy without independent duplicate/nonduplicate labels risks substituting
one arbitrary identity assumption for another. Future work should quantify
partition stability under predeclared location/time noise distributions and
measure identity error and continuity on authorized labeled data.
