# E429 | Timezone-aware observation timestamps at the input boundary

**Date:** 2026-10-30. **Scope:** observation model input and SQLite replay, stacked on E428 PR #44. No production changes or correspondence.

## Falsifiable failure and negative reproduction

The pre-E429 `Observation` model used plain `datetime` for `observed_at` and `ingested_at`. Pydantic 2.13.5 accepted ISO 8601 timestamps without an offset (e.g. `2026-10-30T12:00:00`). A local source-equivalent reproduction accepted and serialized those values; subtracting an aware UTC `datetime.now(UTC)` from the naive event timestamp raised `TypeError: can't subtract offset-naive and offset-aware datetimes`.

The same arithmetic is used by `freshness`, `build_hotspots`, `build_hotspots_as_of`, and source-health calculations. SQLite previously persisted the naive timestamp unaltered. This is a deterministic ingestion/replay crash risk, **not** evidence of a live production incident.

## Minimal change

- Use Pydantic's `AwareDatetime` for both `Observation.observed_at` and `Observation.ingested_at`.
- Preserve explicit timezone offsets (including +05:30) and existing UTC-aware default factories; do not silently guess a timezone for offset-free input.
- Add regression coverage for naive Python and ISO strings, model replay, default UTC, and an aware-offset SQLite round trip followed by historical fusion.
- No API, DB schema, historical data, external systems, or deployment changes.

## Validation and limitations

- **Pre-fix reproduction:** naive timestamps accepted; aware-minus-naive arithmetic raised `TypeError`.
- **Local source-equivalent Pydantic 2.13.5 mirror:** 8/8 checks passed, covering rejection of naive strings/datetimes, acceptance of explicit Z and +05:30 offsets, default UTC, JSON round trip, and aware arithmetic.
- **Exact repository tests, Ruff and CI:** **NOT RUN**. The GitHub billing email dated 2026-10-29 reports 2,000/2,000 included Actions minutes used. Commits carry `[skip ci]` to avoid initiating potentially billable workflows.
- Existing databases containing legacy naive timestamps will now fail closed on load; **inventory and an explicitly approved timezone migration are required before production adoption**. Never assume naive historical times are UTC.
- Authentication, provenance, and event-time/ingestion-time trust remain separate open issues.

## Next gate

Run `python -m pytest -q tests/test_e429_aware_observation_timestamps.py`, the full repository test suite, and Ruff in a verified no-charge environment. Test against a copy of any existing SQLite store to identify legacy naive timestamps before review or merge. The E413-E429 stack remains unmerged.
