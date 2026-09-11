# Utsav Footprint

Open-source software for measuring, fusing and acting on festival externalities without pretending software is a magical physical sensor.

The core is a **virtual sensor network** that combines citizen reports, authorised CCTV-derived candidates, partner measurements, official public data and satellite/remote-sensing products into live hotspot state with explicit uncertainty and provenance.

## What is implemented

- FastAPI ingestion API and WebSocket stream
- geospatial/temporal hotspot clustering
- confidence + freshness decay
- mass-range fusion without double-counting repeated reports
- provenance classes: `verified_official`, `measured`, `observed`, `modelled`
- material probability fusion
- unresolved-waste-hours metric
- authorised CCTV persistent-change adapter (candidate generator, not automatic waste truth)
- STAC satellite scene discovery adapter
- generic official JSON/CSV adapter
- live Leaflet map dashboard
- tests + CI + Docker

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,cctv]'
uvicorn utsav_sensor.api:app --reload
```

Open `http://127.0.0.1:8000/`.

Inject demo observations:

```bash
python scripts/demo_feed.py
```

## Sensor contract

Every observation must say what it really is. A model estimate is never relabelled as a measurement. A satellite scene is never called a waste detection unless a detector actually produced one. A CCTV candidate is only a candidate until another source confirms it.

`confidence != truth` and `precision != accuracy`.

## Source hierarchy

| Provenance | Typical source | Base weight |
|---|---|---:|
| `verified_official` | signed/traceable authority record | 1.00 |
| `measured` | scale, lab, cleanup partner | 0.98 |
| `observed` | citizen / verifier evidence | 0.80 |
| `modelled` | CV / remote-sensing inference | 0.35 |

## Privacy and CCTV

The CCTV adapter only connects to camera URLs explicitly provided by the operator. It does **not** scan the internet for cameras or bypass authentication. Frames are processed in memory by default and are not uploaded or retained. The built-in detector emits persistent-change candidates, because generic computer vision cannot honestly infer kilograms of festival waste from pixels alone.

## Satellite reality

Sentinel/Landsat-class imagery is useful for large dumps, water-surface changes and regional context, not a plastic bag on a Mumbai lane. `stac.py` discovers imagery and keeps acquisition/cloud metadata so remote-sensing models can be plugged in later without fabricating detections.

## API

- `POST /v1/observations`
- `GET /v1/observations`
- `GET /v1/hotspots`
- `GET /v1/hotspots/{id}`
- `WS /v1/stream`
- `GET /healthz`

## License

Apache-2.0.
