"""E496: public API exposes immutable-ID conflicts as HTTP 409."""
from fastapi.testclient import TestClient

from utsav_sensor import api
from utsav_sensor.errors import ObservationConflictError


def test_http_conflicting_observation_id_returns_409(monkeypatch):
    async def reject_conflict(_observation):
        raise ObservationConflictError("observation ID already exists with different evidence")

    monkeypatch.setattr(api.engine, "ingest", reject_conflict)
    response = TestClient(api.app).post(
        "/v1/observations",
        json={
            "id": "e496-conflict",
            "source_type": "citizen",
            "provenance": "observed",
            "source_id": "synthetic",
            "lat": 19.076,
            "lon": 72.8777,
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "observation ID already exists with different evidence"
