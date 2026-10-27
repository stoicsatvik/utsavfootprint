# E336 | Pairwise hotspot linkage and temporal-span falsification

Date: 2026-10-27. Research-only synthetic geometry. No field measurements, waste mass ground truth, deployments, or physical performance claims.

## Question and frozen comparison

Does a centroid-radius threshold of 120 m plus a 24-hour newest-observation time check guarantee that all observations assigned to a hotspot are within 120 m of one another and within one 24-hour interval? **No.**

Reproduce the pre-E336 rule independently in `tests/test_e336_cluster_linkage.py`. Compare against (1) the corrected production greedy algorithm with explicit all-pairs spatial and full-cluster temporal caps, (2) independent agglomerative complete-link reference, and (3) a transitive neighbour connected-components reference analogous to DBSCAN minPts=1. The references are comparators, **not ground truth**.

All coordinates, timestamps, and confidence/mass fields are deterministic synthetic fixtures. Haversine uses a spherical Earth of radius 6,371,000 m. The comparisons are not a validation of real festival waste or sensor accuracy.

## Adversarial counterexamples

| Fixture | Pre-E336 centroid/newest-only rule | E336 pairwise/time-span guard | Independent reference |
|---|---|---|---|
| Equatorial 0, 100, 165, 205 m chain, same time | 1 cluster, 205 m diameter despite 120 m nominal radius | 2 clusters of 2; 100 m and 40 m diameters | Complete-link: 2 clusters; connected-components: 1 overmerged cluster |
| Identical chain crossing longitude +180/-180 | 1 cluster, 205 m diameter | 2 clusters of 2 | Complete-link: 2 clusters |
| Co-located observations at hours 0, 23, 46 | 1 cluster spanning 46 hours despite 24-hour window | 2 clusters, maximum span 23 hours | Complete-link: 2 clusters |
| Compact 0, 40, 80 m | 1 cluster | 1 cluster | Complete-link: 1 cluster |
| Separate 0, 300, 600 m | 3 clusters | 3 clusters | Complete-link: 3 clusters |
| Near-pole pair separated by about 111.2 m | 1 cluster | 1 cluster | Spherical geometry preserved |

The source code previously checked only distance to the evolving centroid and age against the latest observation, not the complete cluster diameter or full temporal span. This makes the 120 m and 24 h settings *centroid-acceptance heuristics*, not guaranteed pairwise bounds.

## Change and deliberately preserved negative finding

The production `cluster_observations` function now rejects any append that would violate either all-pairs great-circle distance or the min-to-max observed-time span. It retains the spherical centroid as the best-eligible-cluster selection criterion and leaves the API contract unchanged.

**Remaining limitation:** Greedy grouping still depends on stable observation-ID order for some three-point chains. Renaming otherwise identical observations can change which neighbouring pair is grouped. This is explicitly regression-tested, not hidden. An order-independent agglomerative replacement could improve this, but would change hotspot identity/continuity and needs a separate migration and precision/recall assessment.

The guard can split a real physical pile that extends beyond 120 m. No source-derived or independently measured pile labels exist to estimate the overmerge/oversplit tradeoff. Treat conservative splitting as a bounded software invariant, **not** improved real-world detection accuracy.

## Reproduction and validation

Run `pytest -q tests/test_e336_cluster_linkage.py`, then `ruff check src tests scripts && pytest -q`. The seeded 64-case fuzz control checks that no output cluster exceeds the configured spatial or temporal caps and that all observations are represented once. No network access or external dataset is needed.

**Claim:** Pre-E336 radius/time-span invariants REJECTED by exact synthetic counterexamples. E336 caps SUPPORTED IN TESTED SOFTWARE by exact-head CI. Hotspot truth, independence, physical mass and field accuracy NOT YET PROVEN.

**Next:** Compare independent complete-link, density-based and ID-invariant clustering on consented/authorised geolocated observations with verified duplicate/nonduplicate labels; quantify overmerge/oversplit and hotspot-ID stability before any deployment.

## Exact-head CI receipt

[Actions run #40552217449](https://github.com/stoicsatvik/utsavfootprint/actions/runs/40552217449) passed Ruff and the complete 25-test suite on commit `6a525580502bbae5df35b3d4699791cf119f7de8`. The first test-containing push failed Ruff C414 (unnecessary list around sorted); this was corrected without deleting the failure history. The source-only push passed before tests were added. This receipt validates the same experiment code; the report-only commit after it does not change executable code.
