# E468 | Reopened hotspot confidence must not inherit pre-cleanup evidence

Date: 2026-11-01. **Synthetic numerical falsification only**. This is not a verified cleanup, authenticated source, independent field measurement, or deployment.

## Question and negative result

Can an old high-confidence measured observation make a newly reopened pile appear strongly verified despite weak current-episode evidence?

**Yes, in E464 source.** With T-3h measured provenance and confidence 1.0, T-2h declared official cleanup with confidence 0, and T-1h observed provenance with confidence 0.05, the pre-change source-equivalent confidence calculation yields:

- Historical measured strength: **0.582711486**
- New observed strength: **0.033635857**
- Pre-change cumulative confidence: **0.596747343**
- Confidence supported by the new episode alone: **0.033635857**
- Apparent inflation: **17.741×** in this adversarial fixture

The first independent arithmetic check used an incorrect threshold `legacy > 0.6` and failed; the actual value is approximately 0.59675. The corrected numerical assertions passed. The discrepancy is preserved here rather than rounded into a passing claim.

## Narrow code change

Reuse E460/E464's already-established credible-closure boundary and strict post-closure `mass_episode` for **confidence only when reopened**. Keep historical confidence unchanged for closed or never-credibly-closed hotspots. Keep `observation_count` and `independent_sources` as historical audit counts, not current-episode counts. Preserve existing centroid and location identity semantics, material and mass logic, status, and timestamps.

Same-time closure/open events are ambiguous: no strictly later evidence means current-episode confidence zero. This is a conservative evidence abstention, not proof that a hotspot does not exist.

## Validation and limitations

- A separate Python source-equivalent arithmetic harness passed **5/5** focused controls: reopened old-source inflation, closed-history retention, unverified cleanup, reused source, and ambiguous same-time abstention. **It is not the committed repository code.**
- Five deterministic pytest contracts are committed in `tests/test_e468_reopened_confidence_epoch.py`, but native pytest, inherited suite, Ruff, and exact-head CI have **not run**.
- No new GitHub Actions workflow was deliberately triggered; commits include `[skip ci]` to avoid possibly billable infrastructure.
- The previous E464 nine-test suite is also not yet verified by native execution.
- No independent provenance authentication or physical pile-identity resolution exists; an attacker could still claim official cleanup.
- Centroid continues to incorporate pre-cleanup observations, which may be appropriate for hotspot identity but not for a current-pile coordinate. Define and test this separately, rather than silently altering it here.

## Next falsification gate

Run `python -m pytest -q tests/test_e468_reopened_confidence_epoch.py tests/test_e464_reopened_material_epoch.py tests/test_reopened_mass_epoch.py`, then `ruff check src tests scripts` and `pytest -q` in a verified no-cost environment. Investigate same-time ambiguity, multi-episode reopening, and old high-strength centroid contamination independently before merging.


## 2026-11-01 follow-up: native focused regression execution (E469 audit)

A local, **offline** validation workspace was assembled from the **exact GitHub blobs** of the E468 branch. Git blob hashes were independently recomputed on the local bytes before execution:

| File | Git blob SHA |
| --- | --- |
| `src/utsav_sensor/models.py` | `68cee79bb90dead35dcabc0cb0aa3f74623fe45e` |
| `src/utsav_sensor/fusion.py` | `14276530d75682eeec3285a61ad6393252c8d90a` |
| `tests/test_reopened_mass_epoch.py` | `4ad1c70891650fc37577639399184395b7dfb698` |
| `tests/test_e464_reopened_material_epoch.py` | `22e4d5fb1d63fac777e1c1441a127582e4004aed` |
| `tests/test_e468_reopened_confidence_epoch.py` | `0db0908068c0ec59a4d9008a83c7bffbe78d6f7a` |

Command: `PYTHONPATH=src python -m pytest -q tests/` in the isolated workspace, Python 3.13.5, Pydantic 2.13.5, pytest 9.0.2. **21/21 passed in 0.12 seconds**: E460 7/7, E464 9/9, E468 5/5. This supersedes the prior claim that these committed tests had never run. **Not** full-repository pytest, Python 3.12 CI, Ruff, or an installed-package/integration test. The isolated workspace contained the two exact production source blobs and the three exact test blobs, not the complete repository. No GitHub Actions minutes or external infrastructure used.

**Additional falsification of current centroid semantics, not a code fix:** In the same exact-source workspace, an old strong measured report at (19.076, 72.8777), a zero-confidence declared official cleanup, and a weak new report 94.58 m east remained one spatial cluster; its returned centroid was **89.42 m away from the new report**. The current confidence was correctly **0.03364**. This proves that the current hotspot coordinate can represent historical identity rather than the location of the current pile. Because the API has only one `lat/lon` pair, changing it silently would alter identity/display semantics. Define a separate current-episode location contract and tests before modifying runtime code. This is a synthetic geographic counterexample, not field accuracy evidence.

**Still blocked:** complete inherited regression suite, Ruff, CI, physical cleanup authentication, and user-facing map semantics. No merge or deployment.
