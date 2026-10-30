# E410 | Hotspot resolution-episode falsification

**30 October 2026. Synthetic software lifecycle tests only, not real festival/cleanup evidence.**

## Question

Does an old open report permanently inflate unresolved-waste-hours after a later cleanup report, and can an unverified citizen cleanup assertion make the displayed status contradict the unresolved metric?

## Expected-red reproduction

At frozen `NOW = 2026-10-30 08:00 UTC`, all observations share a synthetic Mumbai coordinate and a 10–12 kg mass range. The unchanged E392 implementation computed `unresolved = any(report not closed)` and measured duration from the oldest report, while displaying the most recent report's status.

| Sequence | Pre-fix displayed state | Pre-fix unresolved hours | Expected conservative state |
|---|---|---:|---|
| open 4h ago; declared measured cleanup 2h ago | cleaned | 4 | cleaned, 0h |
| same, then new open 1h ago | open | 4 | open, 1h |
| open 4h ago; citizen says cleaned 2h ago | cleaned | 4 | open, 4h |
| open 5h; cleanup 4h; claimed 2h; declared official verified 1h | verified | 5 | verified, 0h |

[Test-first Actions #40998123548](https://github.com/stoicsatvik/utsavfootprint/actions/runs/40998123548) failed **four E410 tests** while **36 inherited tests passed**; Ruff was clean. The fifth initial test happened to pass under the original insertion order, so it is not counted as a pre-fix falsification.

## Conservative isolated-branch correction

`_resolution_episode` treats only `cleaned/verified` events **declared** `measured` or `verified_official` as closures. Old open reports before the latest such closure no longer keep the hotspot unresolved. Open/claimed/cleaning reports at or after that closure start a new unresolved episode. Same-timestamp open versus closure is resolved conservatively as open, independent of list order. An unverified citizen cleanup claim alone cannot close an earlier open episode.

This does **not authenticate provenance**. The API currently accepts provenance labels; a malicious or mistaken source could claim a measured/official status. Ingestion authorization, independent verification and physical pile identity remain unresolved.

The patch changes only hotspot fusion logic on an isolated research branch. No live observations or infrastructure were modified.

## Validation

- [First corrected exact-head CI #40998155373](https://github.com/stoicsatvik/utsavfootprint/actions/runs/40998155373): **SUCCESS**, 40 pytest tests and Ruff.
- [Expanded exact-head CI #40998326965](https://github.com/stoicsatvik/utsavfootprint/actions/runs/40998326965): **SUCCESS**, **41 pytest tests** and Ruff, including all lifecycle and order-invariance controls.

## Claim states

- Original status/unresolved-hours consistency: **REJECTED IN SYNTHETIC SOFTWARE**.
- Conservative declared-provenance resolution episodes: **SUPPORTED IN TESTED SOFTWARE**.
- Source authentication, real cleanup accuracy, true pile identity, false-close rate, field validity: **NOT YET PROVEN**.

**Next:** source-authenticated resolution events, independent same-pile versus different-pile labels, and held-out event-order/time perturbations. Measure false closures and delayed reopenings before integrating into production. No merge, deployment, field collection or contact.
