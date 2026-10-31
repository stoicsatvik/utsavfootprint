# E460 | Reopened hotspot mass must not inherit pre-cleanup evidence | 2026-11-01

## Falsification question
Can a credible cleanup followed by a new open observation cause the mass fusion engine to reuse a high-provenance measurement from the *previous* pile? The source-level answer before this change is **yes**.

## Frozen synthetic counterexample
At T-3h: partner `measured` 100–120 kg, open. At T-2h: `verified_official` cleaned. At T-1h: citizen `observed` 2–4 kg, open. The old `_fuse_mass` ranked the historical measured interval above the new observation and returned 100–120 kg for the newly reopened hotspot. This is not a real-world observation.

## Change
Preserve `_resolution_episode` status semantics. When a declared measured/official closure is followed by an open event at or after its timestamp, restrict mass candidates to *strictly after* the latest closure. The strict boundary refuses to attribute ambiguous same-timestamp cleanup mass to a reopened pile. Preserve historical mass on closed hotspots and preserve all original behavior without a credible closure. Source provenance labels are not authenticated; this is an internal temporal consistency correction, **not** evidence of real cleanup.

## Controls
Seven deterministic regression cases: new low-priority mass, no new mass (abstention), no closure, closed historical mass, unverified citizen cleanup, same-time ambiguity, and repeated closures. Independent source-equivalent Python reproducer demonstrates the old/new discrepancy; full committed suite and CI status must be recorded separately after execution.

## Claim
**REJECTED:** mass interval from a prior declared-cleaned episode is a current reopened-pile estimate. **SUPPORTED IN SYNTHETIC SOURCE-EQUIVALENT TESTS:** epoch filtering avoids this reuse. **NOT YET PROVEN:** correctness of physical pile identity, independently authenticated source provenance, real-world mass accuracy or downstream UX.

## Next
Run the exact committed pytest and CI; test out-of-order ingestion, same-source reports, cluster split/merge and authentic cleanup evidence with explicit independent labels. Do not deploy or treat an unverified cleanup assertion as physical truth.
