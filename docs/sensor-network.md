# Sensor network operating model

The network is a hierarchy of evidence, not one omniscient sensor.

## Layer 0: physical truth

Waste, water quality, air quality, noise and cleanup state exist in the physical world. Software can only observe them through instruments or evidence.

## Layer 1: edge sources

- citizen phones: photo/location/time + human classification
- cleanup teams: weighed mass + before/after evidence
- authorised CCTV: persistent-change candidates, optionally a validated waste classifier
- municipal/authority feeds: official records and complaint state
- satellite imagery: large-scale context and validated remote-sensing products
- laboratory/sensor partners: water/air/noise measurements

## Layer 2: source health

`GET /v1/sources` exposes whether each source is live or stale. A map point without a fresh source is not allowed to masquerade as live data.

## Layer 3: fusion

The fusion engine clusters observations in space/time, preserves provenance, prevents repeated reports of the same pile from being summed, decays stale evidence and calculates a hotspot confidence score.

## Layer 4: persistence and audit

The default build persists every observation to SQLite so restarts do not erase the city. Postgres/Supabase is the scale-up storage target.

## Layer 5: outputs

- `/v1/hotspots`: current fused state
- `/v1/stream`: push updates
- `/metrics`: machine-readable operational metrics
- map dashboard: human view
- future alert/action engines: cleanup dispatch, complaint routing and clean-exit scoring

## NASA / satellites

`POST /v1/satellite/nasa/search` queries NASA Earthdata CMR STAC metadata. The caller supplies a bounding box, time range and optional collection names. The response exposes acquisition time, footprint, cloud cover and asset links.

Satellite data enters the waste state only after a domain model produces a justified observation. Street litter is generally smaller than public Earth-observation pixel sizes, so the default adapter deliberately refuses to manufacture a waste estimate from scene metadata alone.

## CCTV fleet

Run one adapter per authorised camera or containerise them as edge agents. They submit candidate observations to the central API over HTTP. The default detector stores no frames and performs no facial recognition.
