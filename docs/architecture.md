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
