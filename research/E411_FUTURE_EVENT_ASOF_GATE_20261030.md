# E411 | Future-dated closure contamination of as-of hotspot snapshots

**30 October 2026. Synthetic software falsification, not verified waste cleanup or field evidence.**

## Falsifiable question

Can an observation whose `observed_at` is *after* the requested `now` resolve a currently open hotspot or create a hotspot that does not yet exist?

## Pre-fix counterexample

Freeze `now = 2026-10-30 08:00 UTC`. Put two synthetic observations at the same Mumbai coordinate:

- `open` at 04:00 UTC, provenance `observed`;
- `cleaned` at 10:00 UTC (two hours **after** the snapshot), provenance **declared** `measured`.

The E410 `_resolution_episode` selects the later closure and returns `('cleaned', 0.0)`, whereas the single currently observable report returns `('open', 4.0)`. The previous `build_hotspots` 72-hour filter used only `now - observed_at <= 72h` and therefore also included future reports. A future-only verified report could create a current hotspot. A local source-equivalent Python reproduction confirmed the incorrect closed result. The repository's test-first red commit was **not executed** due to Actions-minute exhaustion.

## Bounded correction

`build_hotspots` excludes observations more than five minutes in the future from the as-of view; stored observations are **not deleted** and can become eligible later. Direct `fuse_cluster` raises `ValueError` for such future observations rather than silently creating an inconsistent snapshot. The five-minute clock-skew allowance is explicit, not empirically calibrated. Observations inside that tolerance can still affect an as-of state early; strict historical snapshot correctness is **not established**.

Added five deterministic tests for future closure contamination, future-only hotspots, direct-fusion rejection, past cleanup preservation and one-second clock skew.

## Validation and claim boundaries

- Pre-fix selected source-equivalent counterexample: **reproduced** (`cleaned, 0h` versus `open, 4h`).
- Corrected source-equivalent Python mirror: **5/5 focused checks passed**.
- Actual repository pytest, Ruff, complete inherited suite and exact-head CI: **NOT RUN**. GitHub billing alert on 29 October indicated 2,000/2,000 included Actions minutes consumed. Commits use `[skip ci]` to avoid intentionally consuming more minutes.
- No authenticated provenance, real-world pile identity, field false-close rate, ingestion authorization or real cleanup evidence is established. The five-minute tolerance is an explicit limitation.

## Next experiment

Use frozen synthetic clock-skew sweeps (0, 1, 5, 6, 60, 120 minutes), independently labeled event ordering and an authenticated-source design. Compare strict as-of exclusion against delayed ingestion/buffering; quantify false early closures, latency and completeness. Run exact repository pytest/Ruff after confirming a no-charge Actions budget. Do not merge the stacked draft before that validation.

No live data mutation, deployment, external contact or financial commitment.
