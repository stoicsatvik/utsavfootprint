from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field, model_validator

from .adapters.nasa import search_nasa_scenes
from .engine import SensorEngine
from .models import Observation
from .store import SQLiteObservationStore

store = SQLiteObservationStore(os.getenv("UTSAV_DB_PATH", "data/utsav.db"))
engine = SensorEngine(store)
_streams: set[asyncio.Queue] = set()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await engine.start()
    yield


app = FastAPI(title="Utsav Footprint Sensor API", version="0.2.0", lifespan=lifespan)


class SatelliteSearchRequest(BaseModel):
    bbox: tuple[float, float, float, float]
    start: datetime
    end: datetime
    collections: list[str] = Field(default_factory=list)
    provider: str = "LPCLOUD"
    limit: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def valid_window(self):
        if self.start > self.end:
            raise ValueError("start must not be after end")
        west, south, east, north = self.bbox
        if west >= east or south >= north:
            raise ValueError("bbox must be (west, south, east, north)")
        return self


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
    return {"ok": True, "sensor": "utsav-footprint", "version": "0.2.0"}


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


@app.get("/v1/sources")
async def sources():
    return await engine.source_health()


@app.post("/v1/satellite/nasa/search")
async def nasa_search(request: SatelliteSearchRequest):
    return await search_nasa_scenes(
        request.bbox,
        request.start,
        request.end,
        request.collections,
        request.provider,
        request.limit,
    )


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    obs = await engine.observations()
    hs = await engine.hotspots()
    low = sum(h.unresolved_waste_hours_low or 0 for h in hs)
    high = sum(h.unresolved_waste_hours_high or 0 for h in hs)
    lines = [
        "# TYPE utsav_observations_total gauge",
        f"utsav_observations_total {len(obs)}",
        "# TYPE utsav_hotspots_total gauge",
        f"utsav_hotspots_total {len(hs)}",
        "# TYPE utsav_unresolved_waste_hours_low gauge",
        f"utsav_unresolved_waste_hours_low {low}",
        "# TYPE utsav_unresolved_waste_hours_high gauge",
        f"utsav_unresolved_waste_hours_high {high}",
    ]
    return "\n".join(lines) + "\n"


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
