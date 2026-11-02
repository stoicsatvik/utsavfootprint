# E501 | Actual `put()` process-death boundary experiment

Date: 2026-11-02. Continuation of E499/E500, stacked in draft PR #54. This remains research-only; no public endpoint, production persistence, deployment, or merge is changed.

## Motivation and falsifiable hypothesis

E500 directly inserted into the same SQLite table but did **not** execute `ResearchFirstReceiptStore.put()`. E501 tests the actual `put()` control flow at the two COMMIT boundaries.

**Hypothesis:** with a single SQLite database file, killing a child process immediately before its actual `put()` COMMIT leaves no visible partial first receipt, while killing it immediately after COMMIT leaves a persistent first receipt that an exact-evidence retry cannot restamp.

## Experiment

`tests/test_e501_actual_put_crash.py` spawns a separate Python process, initializes the real research store, and wraps that child's `sqlite3.connect` return value. The wrapper delegates real SQLite operations and exits with code 17 immediately before or immediately after the `COMMIT` executed by the unmodified `put()` method. Exit code 91 is a failure sentinel if the intended boundary is never reached. The parent reopens the database and verifies the receipt and retry invariants.

This is stronger than E500's hand-constructed SQL transaction, but it is still **synthetic fault injection**, not a random crash, a real power cut, or a proof of durable storage hardware behavior. The wrapper is confined to the child; the application implementation is not modified.

## Results

- Local source-equivalent validation with Python 3 and Pydantic 2: **2/2 passed**. The local fixture used a minimal Observation model, not the full repository model. Exact-head GitHub Actions validation is required separately.
- Pre-COMMIT process death: uncommitted row is absent; subsequent normal `put()` succeeds.
- Post-COMMIT process death: first receipt survives; a retry with the same immutable evidence preserves the original timestamp.

## Preserved negative boundaries

- This does not establish power-loss durability, `fsync` or controller write-cache guarantees, multi-host consistency, trusted monotonic clocks, authenticated issuer identity, or Sybil resistance.
- The wrapper intercepts `execute("COMMIT")`; it does not cover every bytecode-level crash point, corruption, disk exhaustion, or a connection interruption in the middle of SQLite's native COMMIT.
- Client `observed_at` must remain stable for exact-ID retries, and legacy client-controlled timestamps remain untrustworthy.

## Next decision gate

Run exact-head Ruff and the full pytest suite. Keep PR #54 draft. Before production integration, define a versioned receipt contract and test storage durability under actual restart/failure conditions with a trusted clock and authenticated issuers.

## Exact-head repository validation

At commit `c787b010bba3828226ffbaff8c10a7bf07d80adf`, both [PR CI #41434125090](https://github.com/stoicsatvik/utsavfootprint/actions/runs/41434125090) and [push CI #41434116660](https://github.com/stoicsatvik/utsavfootprint/actions/runs/41434116660) succeeded. The PR job log reports **Ruff: all checks passed; pytest: 199 passed, 1 nonfatal warning in 3.05s** (197 inherited plus 2 new). This verifies the real repository's model and dependencies on GitHub Actions; it does not remove the power-loss, issuer, or distributed-consistency limitations above. This documentation-only update requires a new final-head CI result.
