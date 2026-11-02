# E498 | Anonymous aliases and backdated ingestion falsify evidence independence

Date: 2026-11-02. Research-only continuation of E497 draft PR #52. No production ingestion changes, deployment, or merge.

## Trigger and falsifiable question

BuildWithSatvik's substantive spectroscopy correspondence has already been acknowledged; no new human review was found on the active research PRs. E497 restricted unauthenticated POST requests to citizen/observed/open-or-candidate, but its negative controls showed that the public route still accepts arbitrary `source_id`, `confidence`, and `ingested_at`.

Can one anonymous caller submit multiple syntactically distinct citizen sources and increase `independent_sources` and fused confidence? Can it backdate `ingested_at` to make an observation appear in a historical as-of snapshot before the actual submission?

## Method

Use FastAPI TestClient against the real public route and an isolated in-memory SensorEngine. Submit eight synthetic reports at the same location and event time, first with one repeated source ID, then with eight caller-chosen source IDs. Read the real hotspot API. Separately, submit a synthetic 2020 observation with a client-provided 2020 ingestion timestamp, reconstruct an as-of 2020 snapshot, and compare it to the same observation with an actual server-side arrival time.

Tests: `tests/test_e498_anonymous_evidence_falsification.py`.

## Expected falsification and interpretation

- Eight reports from one claimed source should produce `independent_sources=1` and confidence near 0.8.
- The same anonymous client using eight claimed IDs should produce `independent_sources=8` and confidence above 0.99. This is **not** eight independent humans or sensors; it is an unauthenticated string-counting artifact.
- A 2020 client-supplied `ingested_at` should make the synthetic observation visible in a 2020 historical snapshot. Replacing it with the actual server arrival time should remove it from that snapshot.

These tests deliberately **pass while demonstrating unresolved trust failures**. They do not claim field exploitation, authenticated identities, real observations, or a validated Sybil-resistant design.

## Why no production patch yet

The E496 immutable-ID contract treats an observation as an immutable record. Simply overriding `ingested_at` on each retry would make otherwise identical retries conflict, and silently changing historical semantics could break clients. The `independent_sources` and confidence metrics likewise need an issuer-verification policy, not a cosmetic clamp or ungrounded per-IP heuristic. Keep the findings on a draft stacked branch until the API contract, identity model, and migration strategy are reviewed.

## Next decisive experiment

Design and test a server-issued first-ingestion timestamp with exact-ID idempotent retries and conflict rejection across concurrent processes. Separately define authenticated issuer IDs, deduplication, and confidence semantics. Until then, display `independent_sources` as **distinct claimed source IDs**, not independent verified reporters, and treat anonymous confidence as unverified.

## Validation

Run `ruff check src tests scripts`, `pytest -q tests/test_e498_anonymous_evidence_falsification.py`, and `pytest -q` at the exact branch head. Record failures and CI separately; no results are asserted before execution.
