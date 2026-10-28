# E371 | A symmetry obstruction to deterministic single-partition hotspot identity

Date: 2026-10-29. **Synthetic, exact combinatorial experiment.** No field observations, real waste-pile labels, user data, CCTV, model-generated detections or physical measurements.

## Question

E349 preserved a software ambiguity: at synthetic eastward offsets 0/100/200 m and a 120 m all-pairs cap, the middle report can join either endpoint, and a 2-microsecond timestamp perturbation switches the chosen group. Could another deterministic sorting/tie-breaking rule guarantee both physically symmetric treatment and maximal pair grouping on this case?

## Frozen abstract model and exact enumeration

Represent three simultaneous synthetic reports by the path compatibility graph `0--1--2`: endpoints are 200 m apart, while each adjacent pair is 100 m apart. A cluster is valid iff **every pair** in it is compatible. Score each partition by the number of unordered observation pairs assigned to the same cluster. This score is an **analyst-chosen combinatorial surrogate**, not a measure of physical pile accuracy.

`python scripts/e371_partition_symmetry.py` enumerates all five set partitions of three vertices and filters them by the clique constraint. Exactly three remain: all singletons, `{0,1}|{2}`, and `{0}|{1,2}`. The two nontrivial partitions tie at score 1. Reflection `0 <-> 2` preserves the compatibility graph and exchanges the two score-maximizers. Neither is fixed by reflection. The only reflection-fixed valid partition is all singletons (score 0).

Therefore, **for this frozen symmetric graph and score**, there is no deterministic *single-valued* clustering function that simultaneously (a) returns a score-maximizing partition and (b) is equivariant under the endpoint-swap automorphism. This is a finite mathematical obstruction, not a probabilistic observation. Choosing one side by absolute longitude, timestamp, ID, or ingestion order breaks at least one symmetry/robustness requirement. A set-valued ambiguous output, an explicit abstention, or extra independent identity evidence is required if that symmetry matters.

## Controls and reproducibility

Three local pytest checks cover all valid partitions, the reflection exchange, and complete/empty graph controls. The experiment is dependency-free and deterministic; the repository's existing CI runs `pytest -q` and `ruff check src tests scripts`. Preserve the JSON stdout as a reproducible synthetic receipt. No change to production clustering, API, data store or deployment.

## Boundaries and next gate

- **PROVEN for this abstract three-node graph/objective:** no reflection-equivariant deterministic single maximizer exists.
- **NOT YET PROVEN:** whether a reflection-invariant output is desirable for real geographic coordinates; whether maximizing grouped pairs correlates with correct physical pile identity; empirical precision/recall, oversplit/overmerge cost, noise robustness or hotspot continuity.
- **Next:** obtain authorized independently labelled duplicate/nonduplicate observations and a predeclared error/cost model. Compare existing greedy, abstaining/ambiguity-aware and alternative linkage policies under identical spatial/time noise, then select a production policy only on measured external utility. Avoid more arbitrary sorting patches without labels.
