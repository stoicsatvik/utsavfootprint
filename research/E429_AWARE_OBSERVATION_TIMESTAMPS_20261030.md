# E429 | Timezone-aware observation timestamps at the input boundary

**Date:** 2026-10-30. **Scope:** observation model input and SQLite replay, stacked on E428 PR #44. No production changes or correspondence.

## Falsifiable failure and negative reproduction

The pre-E429 `Observation` model used plain `datetime` for `observed_at` and `ingested_at`. Pydantic 2.13.5 accepted ISO 8601 timestamps without an offset (e.g. `2026-10-30T12:00:00`). A local source-equivalent reproduction accepted and serialized those values; subtracting an aware UTC `datetime.now(UTC)` from the naive event timestamp raised `TypeError: can't subtract offset-naive and offset-aware datetimes`.

The same arithmetic is used by `freshness`, `build_hotspots`, `build_hotspots_as_of`, and source-health calculations. SQLite previously persisted the naive timestamp unaltered. This is a deterministic ingestion/replay crash risk, **not** evidence of a live production incident.

## Minimal change

- Use Pydantic's `AwareDatetime` for both `Observation.observed_at` and `Observation.ingested_at`.
- Require explicit timezone offsets, then normalize accepted aware timestamps to UTC, matching the already-tested E175 policy; never guess a timezone for offset-free input. This supersedes the original E429 offset-preservation policy.
- Add regression coverage for naive Python and ISO strings, model replay, default UTC, canonical +05:30-to-UTC conversion, an SQLite round trip, and historical fusion.
- No API, DB schema, historical data, external systems, or deployment changes.

## Validation and limitations

- **Pre-fix reproduction:** naive timestamps accepted; aware-minus-naive arithmetic raised `TypeError`.
- **Original E429 local source-equivalent Pydantic 2.13.5 mirror:** 8/8 checks passed for the earlier offset-preserving policy; that policy has now been superseded.
- **2026-10-31 UTC-reconciliation local mirror:** 5/5 checks passed using Pydantic 2.13.5 and SQLite, covering naive rejection, equivalent-instant normalization, and legacy mixed-offset ordering. This is **not** exact repository validation.
- **Exact repository tests, Ruff and CI:** **NOT RUN**. The GitHub billing email dated 2026-10-29 reports 2,000/2,000 included Actions minutes used. Commits carry `[skip ci]` to avoid initiating potentially billable workflows.
- Existing databases containing legacy naive timestamps will now fail closed on load; **inventory and an explicitly approved timezone migration are required before production adoption**. Never assume naive historical times are UTC.
- Authentication, provenance, and event-time/ingestion-time trust remain separate open issues.

## Next gate

Run `python -m pytest -q tests/test_e429_aware_observation_timestamps.py`, the full repository test suite, and Ruff in a verified no-charge environment. Test against a copy of any existing SQLite store to identify legacy naive timestamps before review or merge. Reuse the existing E176/E177 read-only audit on an authorized offline snapshot. E175 PR #11 has the same UTC-normalization policy, but its prior green CI does not validate this stacked branch. The E413-E430 stack remains unmerged.
