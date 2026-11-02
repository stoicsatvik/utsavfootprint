# E497 | Anonymous ingestion must not self-certify privileged evidence

Date: 2026-11-02. Stacked on draft E496 PR #51; draft research branch only, no merge or deployment.

## Feedback and falsifiable question

BuildWithSatvik's only substantive spectroscopy reply was previously acknowledged; there is no new human review on this project. E496 established immutable observation IDs but documented an unresolved trust gap: the unauthenticated `POST /v1/observations` accepts caller-selected `source_type`, `provenance`, and `status`. Could an anonymous client claim to be an official or submit a verified cleanup without credentials?

**Before E497:** yes. The route directly parsed `Observation` and forwarded it to `SensorEngine.ingest`, with no authorization or privilege check. The model accepts `source_type=official`, `provenance=verified_official`, and `status=verified`. This is a code-level authorization gap, not evidence of a real-world exploit.

## Narrow change

The public unauthenticated route now accepts only `source_type=citizen`, `provenance=observed`, and `status=open|candidate`. Other combinations return HTTP 403 *before* any engine/store call. This intentionally changes public API behavior; it is kept on a **draft, unmerged branch** pending integration review. Internal engine/store paths are unchanged, and there is no new privileged ingestion endpoint or authentication claim.

Regression tests cover 12 privileged combinations, two allowed statuses, and two **deliberately passing negative controls**. A synthetic caller can still supply a misleading `source_id`, a self-assessed `confidence=1.0`, and an arbitrary `ingested_at` timestamp. Therefore this change does **not** authenticate users, prevent Sybil submissions, guarantee source provenance, establish time of ingestion, or prevent contradictory new IDs.

## Reproduction

```bash
pip install -e '.[dev]'
ruff check src tests scripts
pytest -q tests/test_e497_anonymous_ingest_trust.py
pytest -q
```

CI should run on the exact stacked branch head. Do not interpret passing synthetic tests as real-world data integrity.

## Pre-existing CI observation

E496's earlier GitHub Actions run #41400597365 failed during test collection with `ModuleNotFoundError: utsav_sensor.errors` at commit `70357e7`; lint passed. The currently fetched E496 branch contains `src/utsav_sensor/errors.py`, but that **does not retroactively validate** the failed commit. Recheck exact-head CI rather than treating earlier failures as resolved.

## Next decisive gate

Introduce a separately authenticated partner/official ingest path with auditable issuer identity, server-issued ingestion timestamps, bounded source confidence, and an explicit migration contract for clients that used the former permissive POST. Test cross-ID Sybil inflation and replay under realistic untrusted reporters before any deployment. No outreach, data collection, or production migration is authorized by this experiment.

## Executed CI validation

The exact code head `ea3a8d1fc9c8d54270e3e6b250ea8aaac314873c` passed [GitHub Actions run #41404144607](https://github.com/stoicsatvik/utsavfootprint/actions/runs/41404144607) on 2026-11-02: `ruff check src tests scripts` succeeded and the full `pytest -q` suite reported **182 passed, 1 warning**. The warning concerns unset `pytest-asyncio` fixture loop scope, not a test failure. This validation covers the E497 guard and all inherited E496 tests. It does not imply authentication or field-data validity.

This report update is documentation-only; verify the resulting final head separately before merge.
