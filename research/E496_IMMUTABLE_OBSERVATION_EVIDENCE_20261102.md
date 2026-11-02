# E496 | Immutable observation IDs prevent silent evidence replacement

Date: 2026-11-02. Synthetic/local software integrity test only. No field data, authentication claim, production migration, or deployment.

## Falsification

The inherited `SQLiteObservationStore._upsert_sync` used `ON CONFLICT(id) DO UPDATE`, while `SensorEngine.ingest` overwrote `self._observations[observation.id]`. Thus a second report with the same ID but different mass, source, provenance, or timestamp could silently replace the first record. The public POST route accepted a caller-provided ID. This is a code-level evidence immutability defect, not proof that anyone exploited it.

## Correction

- SQLite performs insert-or-ignore under its transaction and compares the existing validated Observation on collision. Identical retries are idempotent; conflicting payloads raise a typed `ObservationConflictError` and leave the original stored record unchanged.
- The in-memory engine serializes identity checks and persistence under its lock. Exact duplicate retries do not republish hotspot states.
- The public API maps this typed conflict to HTTP 409 rather than an ambiguous server error.
- Six focused regression cases cover identical retry, mass overwrite, source overwrite, memory-only mode, durable memory+disk consistency, and concurrent conflicting writers.

## Explicit limits

- This does **not** authenticate the submitter or provenance: the unauthenticated API still accepts user-declared `verified_official` / `measured` labels and user-chosen source IDs. These are separate security and trust-model gaps requiring an authenticated ingestion design.
- It does **not** prevent a client from creating a new ID and submitting contradictory evidence. It only prevents rewriting an already accepted ID.
- Historical overwritten records cannot be reconstructed from the existing SQLite table; no claim of recovery.
- The helper/route changes are not deployed, and no live records were modified.
- Native CI should validate the complete stacked research branch before integration.

## Next decisive gate

Freeze an explicit trusted-ingest vs untrusted-citizen boundary, enforce server-assigned ingestion timestamps and authenticated provenance, then test anonymous source-ID Sybil inflation under realistic reporting. No claim of real-world waste measurement or verified cleanup.
