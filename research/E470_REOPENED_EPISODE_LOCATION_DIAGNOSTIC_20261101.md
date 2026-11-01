# E470 | Diagnostic current-episode location without changing hotspot identity

Date: 2026-11-01. **Synthetic software experiment only.** No authenticated cleanup, geolocation accuracy measurement, physical pile identity, deployment, or main merge.

## Falsifiable question

After a declared credible cleanup, can an old high-strength observation displace the historical hotspot centroid far from a weak but positive-strength observation of a reopened pile?

**Yes.** Reusing E468's synthetic reports, the old and new coordinates are 94.579881 m apart. The historical confidence-weighted centroid is **89.418383 m** from the new report. An independent, strictly post-cleanup current-episode candidate is **0 m** from that one new report. This zero is a fixture property, **not** real-world location accuracy.

## Narrow opt-in implementation

New `src/utsav_sensor/episode_location.py` exports `reopened_episode_location(cluster, now)`:

- Retains `HotspotState.lat/lon` as historical cluster-identity coordinates. No API schema, map display, ingestion, or persisted data changes.
- Returns `None` unless a declared measured/official closure is followed by an open report. A citizen's unauthenticated cleanup declaration does not reset the episode.
- Uses **strictly later**, nonterminal observations after the latest credible closure. Equal-time closure/reopening is ambiguous and abstains if no later positive evidence exists.
- Selects one strongest report per source **after** episode filtering, then uses existing spherical positional weighting. Zero-strength reports do not create a claimed current-pile coordinate.
- Raises the same future-clock-skew error as fusion for reports more than five minutes in the future.
- This is a diagnostic candidate for later product-contract review, **not** a second production map coordinate.

## Validation

The exact new helper and test files were executed in an isolated Python 3.13.5/Pydantic 2.13.5/pytest 9.0.2 workspace, with source-equivalent local stubs for the pre-existing `fusion.py` helpers and minimal `Observation` model. **12/12 native helper tests passed**, covering old-evidence exclusion, no/unverified closure, closed state, equal-time ambiguity, zero-strength abstention, source reuse, multiple cleanups, future timestamps, empty input, dateline and input order. `compileall` passed.

The two GitHub file blob SHAs matched the locally tested bytes exactly:

- `src/utsav_sensor/episode_location.py`: `6406de780297017d78c993418e88cf141c715450`
- `tests/test_e470_reopened_episode_location.py`: `931ab001d28845c57539d1d456a39909abe3419c`

**Limitations:** This is not native execution against the exact existing repository `fusion.py` or full `models.py`; their behavior was source-equivalent in the isolated test workspace. Full inherited pytest, Ruff, installed-package integration and exact-head CI remain unverified. No potentially billable GitHub Actions workflow was deliberately started; commits use `[skip ci]`.

## Next decision

Before exposing a new API field, specify whether the consumer needs (1) historical hotspot identity, (2) a current-episode observation centroid, or (3) a physically verified waste-pile position. The first two are software constructs; the third needs authenticated field data and uncertainty bounds. Then run complete native tests and integration checks on a verified no-cost runner. Keep this branch draft and stacked on E468 until the contract is reviewed.
