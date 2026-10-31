# E464 | Reopened hotspot materials must not inherit pre-cleanup classifications

Date: 2026-11-01. Scope: **synthetic evidence-integrity regression**, not physical cleanup verification or real waste-material classification.

## Falsifiable question

Does a declared credible cleanup followed by a new open report allow an earlier high-provenance material label to remain attached to the *new* hotspot episode?

**Yes, in E460 source.** Synthetic sequence: T-3h measured `{"plastic": 1.0}`; T-2h verified-official `cleaned`; T-1h observed `{"glass": 1.0}`. The previous material aggregator iterated representatives from the entire cluster and returned **both** plastic=1.0 and glass=1.0 for the reopened hotspot. A material label absent from all current-episode reports was therefore still presented as current.

## Narrow correction

Reuse E460's existing credible-closure and strict timestamp boundary to select **material evidence from `mass_episode`**, not the entire cluster. Critically, select one strongest representative per source **after** episode filtering: otherwise a stronger pre-cleanup report from a reused source ID could suppress a legitimate post-cleanup material report.

- Reopened after credible closure: only observations strictly later than the latest closure may supply material labels.
- Same-time closure/open boundary: material labels abstain when no unambiguous later evidence exists.
- Closed hotspot or no credible closure: retain historical material behavior.
- Preserve existing mass, status, centroid, combined confidence, observation count, source count and provenance semantics. In particular, **combined confidence and centroid still incorporate historical observations**, which may be inappropriate for an episode-specific interpretation and require a separately specified contract.
- `verified_official` and `measured` are **declared** provenance values, not authenticated proof of real cleanup.

## Validation

A locally executed independent Python source-equivalent reproducer demonstrated the original plastic-label leakage and passed **6/6** focused synthetic controls: reopened, no-new-material, equal-time ambiguity, closed, unverified closure, and same-source replacement. A seventh multiple-cleanup contract is committed as an additional pytest case.

Committed tests: `tests/test_e464_reopened_material_epoch.py` (7 deterministic contracts). **Exact committed pytest, inherited 133-test repository suite and exact-head CI are not yet executed**. Source readback and branch diff should be verified independently. Do not describe the isolated model checks as native integration.

## Next falsification gate

Run `python -m pytest -q tests/test_e464_reopened_material_epoch.py tests/test_reopened_mass_epoch.py` and inherited suite in a no-cost environment. Then separately specify whether current-episode confidence and centroid should exclude pre-cleanup evidence; test out-of-order ingestion, cluster split/merge, and independently authenticated closure labels. Do not merge, deploy or treat a synthetic classification as a field measurement.
