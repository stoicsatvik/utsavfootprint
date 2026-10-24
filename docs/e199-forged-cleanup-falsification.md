# E199: Forged cleanup falsification and opt-in receipt-gated accounting

## Original negative result (preserved)

An independently measured 100–120 kg open observation followed five minutes
later by a citizen-supplied `cleaned` observation causes the E195 place ledger
to report **0 kg current mass**, regardless of whether the citizen observation
claims `modelled` or `observed` provenance. The same closure resets hotspot
unresolved exposure. No authenticated removal evidence was required.

Test-first commit `4276e0c`: [CI #40048208828](https://github.com/stoicsatvik/utsavfootprint/actions/runs/40048208828)
failed **2 synthetic security tests, 15 passed**; Ruff passed.

This demonstrates a software trust-boundary weakness, **not** that any real
citizen report is malicious or that physical waste was actually present.

## Experimental opt-in mitigation

`summarize_coordinates(..., authenticated_closure_digests=frozenset(...))`
now optionally excludes any `cleaned`/`verified` observation whose canonical
SHA-256 content digest is not in an independently authenticated receipt set.
The exclusion is applied *before* place-ledger and hotspot accounting, so an
unattested closure cannot zero current mass or unresolved waste-hours in that
strict query. The result exposes `excluded_unattested_closures`.

The digest includes all observation fields, not merely the producer-controlled
ID, status or provenance. Tests cover modelled and observed forged closures,
a positive authorized closure, and a timestamp-tampered replay with the same
ID. A noncanonical/invalid closure is excluded rather than accepted.

**Default behavior is unchanged** when the optional argument is omitted, to
avoid silently changing existing API consumers and historical reports.

## Critical trust limitations

- **SHA-256 is not authentication.** A producer can hash any fabricated record.
  A separate trusted service must authenticate the complete receipt before
  adding its digest to the allowlist. Never populate the allowlist from the
  same untrusted ingestion payload.
- This is an opt-in **place-summary** accounting boundary, not a system-wide
  correction. Other callers of `build_hotspots` remain vulnerable to forged
  closures; the API endpoint does not yet supply authenticated receipts.
- A forged open report can still bias estimates. Timestamp replay, independent
  source identity, physical cleanup and weighed mass remain unverified.
- Synthetic tests only. No live sensor, production database or authenticated
  receipt registry was accessed.
- E195/E194 are stacked separately from the E187–E192 validation chain.
  Integration must reconcile those branches and run the complete combined
  test suite before deployment.

## Next discriminating experiment

Build a server-owned, append-only cleanup receipt registry whose digest
allowlist is derived from authenticated operator decisions, not from producer
claims. Test replay, forged IDs, altered timestamps, and conflicting closures
across *all* hotspot and place-summary endpoints. Keep this PR draft until
the trust boundary is enforced at ingestion and exact-head CI passes.
