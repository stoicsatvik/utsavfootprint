from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from .engine import SensorEngine
from .models import Observation

app = FastAPI(title="Utsav Footprint Sensor API", version="0.1.0")
engine = SensorEngine()
_streams: set[asyncio.Queue] = set()


def publish(states):
    payload = [s.model_dump(mode="json") for s in states]
    for q in list(_streams):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass


engine.subscribe(publish)


@app.get("/")
async def dashboard():
    path = Path(__file__).resolve().parents[2] / "static" / "index.html"
    return FileResponse(path)


@app.get("/healthz")
async def healthz():
    return {"ok": True, "sensor": "utsav-footprint", "version": "0.1.0"}


@app.post("/v1/observations", response_model=Observation)
async def ingest(observation: Observation):
    return await engine.ingest(observation)


@app.get("/v1/observations")
async def observations():
    return await engine.observations()


@app.get("/v1/hotspots")
async def hotspots():
    return await engine.hotspots()


@app.get("/v1/hotspots/{hotspot_id}")
async def hotspot(hotspot_id: str):
    for state in await engine.hotspots():
        if state.id == hotspot_id:
            return state
    raise HTTPException(status_code=404, detail="hotspot not found")


@app.websocket("/v1/stream")
async def stream(websocket: WebSocket):
    await websocket.accept()
    q: asyncio.Queue = asyncio.Queue(maxsize=4)
    _streams.add(q)
    try:
        await websocket.send_text(json.dumps([s.model_dump(mode="json") for s in await engine.hotspots()]))
        while True:
            payload = await q.get()
            await websocket.send_text(json.dumps(payload))
    except WebSocketDisconnect:
        pass
    finally:
        _streams.discard(q)
