# Virtual Sensor Network Architecture

## Principle

Utsav Footprint estimates a latent physical state from imperfect heterogeneous evidence. The system is therefore closer to sensor fusion than to a CRUD reporting app.

```text
citizen phones ───────┐
authorised CCTV ──────┤
cleanup scales ───────┤
official feeds ───────┤
satellite/STAC ───────┤
water/air feeds ──────┘
                      v
              source normalisation
                      v
             spatiotemporal dedupe
                      v
                hotspot clusters
                      v
          provenance-aware fusion
                      v
 confidence + freshness + uncertainty
                      v
            hotspot digital state
               /       |       \
             map     action    score
```

## Why fusion instead of summation

Five photographs of one 20 kg pile do not create 100 kg of waste. Reports inside one spatiotemporal cluster are observations of one latent state. The reference engine therefore treats repeated reports as correlated evidence. They can add audit history but must not inflate confidence, mass, material probabilities, or hotspot location.

Measured or traceable official quantities outrank pixel-derived estimates. Conflicting evidence remains visible through intervals and provenance instead of being averaged into fake certainty.

## Confidence

For observation `i`:

`strength_i = provenance_weight_i * reporter_confidence_i * media_quality_i * freshness_i`

Freshness uses exponential decay:

`freshness = 0.5 ** (age_hours / half_life_hours)`

Independent-source evidence is fused as:

`confidence = 1 - product(1 - strongest_strength_per_source)`

Repeated messages from the same `source_id` cannot manufacture independence.

## Geospatial replay invariance (E170)

The original greedy clusterer and fused-hotspot coordinates averaged **reports**,
not independent sources. In a synthetic three-source example with positions
19.076°, 19.077°, and 19.078° latitude (same longitude), A and B formed one
120 m cluster and C remained separate. Replaying B 100 times pulled the
intermediate center toward B and incorrectly merged C. Likewise, the fused
A/B center moved from 19.0765° to 19.076990196° without any new source.

The reference implementation now computes one coordinate-wise median over
**distinct (lat, lon) claims per source**, then one contribution per source.
The greedy clusterer uses equal source weights. The fused hotspot center uses
the strongest observation strength per source, with an equal-source fallback
when all strengths are zero. Sources and coordinate pairs are processed in
stable order; repeated identical claims do not move a center.

The seeded regression suite includes 250 synthetic replay/permutation scenarios.
This is a **software replay-invariance property**, not validation of physical
locations. Source IDs can be spoofed, greedy clustering can remain sensitive
to the order/timestamps of *different* coordinate claims, and coordinate-wise
longitude medians are not suitable for antimeridian-spanning observations.
Hotspot IDs, status, unresolved age, and observation counts are outside this
geospatial invariant. Geodetic and provenance policies require separate review.

## Equal-timestamp identifier invariance (E171)

Greedy clustering previously sorted by `(observed_at, observation_id)`.
When three simultaneous observations formed a 120 m chain, merely renaming
IDs changed the partition from `{A,B}, {C}` to `{A}, {B,C}`, even though
sources, coordinates, timestamps, and other evidence were unchanged.

The new tie-break is `(observed_at, lat, lon, source_id, id)`. Thus
chronology remains primary, while random audit IDs cannot decide between
geographic partitions. The final ID key only distinguishes observations with
identical time, position, and source. This is a **narrow deterministic
software invariant**, not a proof that greedy clustering is spatially optimal
or insensitive to timestamps, conflicting coordinates, or source spoofing.

The test-only commit `b131345d` failed as expected in
[CI 39950742034](https://github.com/stoicsatvik/utsavfootprint/actions/runs/39950742034):
**1 failed, 24 passed; Ruff passed**. The negative result is retained.


## North-star metric

For hotspot `h` with mass interval `[m_low, m_high]` and unresolved age `t`:

`UWH_h = [m_low * t, m_high * t]`

Citywide unresolved-waste-hours can be summed only across deduplicated hotspots.

## CCTV

The included adapter is deliberately conservative. It detects persistent scene change, not 'garbage'. A persistent visual change is emitted with `provenance=modelled`, `status=candidate` and low confidence. A future classifier can add material probabilities, but physical mass still requires calibration or measurement.

No face recognition is required. No camera discovery, credential bypass or frame archival belongs in this project.

## Satellite

STAC is the interchange layer. Sentinel-2/Landsat-class imagery is useful for broad environmental context and large accumulations, while street-scale waste is usually below spatial resolution. High-resolution commercial imagery can be added behind the same adapter contract if legally licensed.

## Scale path

Reference v0.1 uses an in-memory engine for zero-friction local execution. Production path:

1. Supabase/Postgres event log for observations.
2. PostGIS or H3 for spatial bucketing.
3. Redis/NATS/Kafka for event fan-out.
4. stateless fusion workers.
5. object storage for opt-in evidence media.
6. append-only provenance/audit records.
7. signed partner/authority ingestion keys.

The fusion package remains deterministic and testable regardless of transport/storage choices.

## Mixed-claim mass replay invariance (E172)

E168 balanced sources but still used the median of *all reports* from each
source. If source A reported distinct mass intervals [100, 110] and [200, 210]
kg while independent source B reported [300, 310] kg, the original fused
interval was [225, 235] kg. Replaying A's second interval under 100 different
report IDs shifted it to [250, 260] kg, without adding independent evidence.

The E172 correction treats an identical (low, high) interval from the same
source as one mass claim, then takes a median over that source's **distinct
intervals**. Distinct claims from the same source can still change its median.
The source-level estimates remain equally weighted, and the original
provenance-rank precedence is unchanged. Interval pairs are deduplicated
together rather than treating bounds as unrelated claims.

The test-only commit `bfa312e` failed as expected in
[CI 39958735208](https://github.com/stoicsatvik/utsavfootprint/actions/runs/39958735208):
**2 new failures, 26 passes, Ruff passed**. The original negative result is
retained in branch history. This is a deterministic software replay-invariance
contract, not proof of calibrated mass measurements, sensor independence,
fraud resistance, or the statistical optimality of a distinct-claim median.
