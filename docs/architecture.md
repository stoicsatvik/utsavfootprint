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

Five photographs of one 20 kg pile do not create 100 kg of waste. Reports inside one spatiotemporal cluster are observations of one latent state. The reference engine therefore uses repeated reports to improve confidence while using robust estimates for mass.

Measured or traceable official quantities outrank pixel-derived estimates. Conflicting evidence remains visible through intervals and provenance instead of being averaged into fake certainty.

## Confidence

For observation `i`:

`strength_i = provenance_weight_i * reporter_confidence_i * media_quality_i * freshness_i`

Freshness uses exponential decay:

`freshness = 0.5 ** (age_hours / half_life_hours)`

Independent-source evidence is fused as:

`confidence = 1 - product(1 - strongest_strength_per_source)`

Repeated messages from the same `source_id` cannot manufacture independence.

## North-star metric

For hotspot `h` with mass interval `[m_low, m_high]` and unresolved age `t`:

`UWH_h = [m_low * t, m_high * t]`

Citywide unresolved-waste-hours can be summed only across deduplicated hotspots.

## Cleanup and reopening lifecycle

A hotspot is an observation history, not a permanently open waste pile. Under
the existing status contract, `cleaned` and `verified` are terminal states.
The most recent event by observation time, then ingestion time and ID, decides
the current status. Terminal states have **zero unresolved-waste-hours** even
when an older observation was open or the terminal report has no mass estimate.

If an open/claimed/cleaning/candidate event arrives after a terminal event,
it begins a new unresolved epoch. Current confidence, material fractions,
location and mass estimates use **only the new epoch's observations**; the
old evidence remains in the historical `observation_ids` and total count.
This prevents an old scale reading or cleanup report from becoming evidence
for a newly observed accumulation. The unresolved clock starts at the first
event of the current epoch, not the first event in the hotspot's history.

These are deterministic accounting rules, not proof that a cleanup physically
occurred. A real deployment must authenticate cleanup/verification sources
and calibrate delayed/out-of-order reporting before interpreting status as
ground truth. Events with identical observation and ingestion timestamps
are ordered by ID solely for reproducibility.

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
