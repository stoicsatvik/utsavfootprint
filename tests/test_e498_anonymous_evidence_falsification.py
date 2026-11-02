"""E498: anonymous source aliases and backdated ingest times are not evidence."""
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from utsav_sensor import api
from utsav_sensor.engine import SensorEngine
from utsav_sensor.fusion import build_hotspots_as_of
from utsav_sensor.models import Observation


def _payload(observation_id: str, source_id: str, observed_at: datetime, **changes):
    result = {
        "id": observation_id,
        "source_type": "citizen",
        "provenance": "observed",
        "source_id": source_id,
        "lat": 19.076,
        "lon": 72.8777,
        "status": "open",
        "confidence": 1.0,
        "observed_at": observed_at.isoformat(),
    }
    result.update(changes)
    return result


def _submit_batch(monkeypatch, *, split_source_ids: bool):
    # Real public HTTP route and real fusion, but isolated in-memory engine.
    monkeypatch.setattr(api, "engine", SensorEngine())
    observed_at = datetime.now(UTC) - timedelta(seconds=2)
    with TestClient(api.app) as client:
        for index in range(8):
            source_id = f"unverified-identity-{index}" if split_source_ids else "same-reporter"
            response = client.post(
                "/v1/observations",
                json=_payload(f"e498-{index}", source_id, observed_at),
            )
            assert response.status_code == 200, response.text
        response = client.get("/v1/hotspots")
        assert response.status_code == 200
        states = response.json()
    assert len(states) == 1
    return states[0]


def test_one_anonymous_caller_can_inflate_apparent_independent_sources(monkeypatch):
    same = _submit_batch(monkeypatch, split_source_ids=False)
    aliases = _submit_batch(monkeypatch, split_source_ids=True)

    assert same["observation_count"] == aliases["observation_count"] == 8
    assert same["independent_sources"] == 1
    assert aliases["independent_sources"] == 8
    assert 0.79 < same["confidence"] < 0.81
    assert aliases["confidence"] > 0.99
    assert aliases["confidence"] > same["confidence"] + 0.15
    # All eight aliases came from the same synthetic unauthenticated client.
    # The field counts claimed source_id strings, not authenticated issuers.


def test_anonymous_client_can_backdate_historical_ingestion(monkeypatch):
    monkeypatch.setattr(api, "engine", SensorEngine())
    past = datetime(2020, 1, 1, tzinfo=UTC)
    as_of = past + timedelta(hours=1)
    with TestClient(api.app) as client:
        response = client.post(
            "/v1/observations",
            json=_payload(
                "e498-backdated",
                "unverified-identity",
                past,
                ingested_at=past.isoformat(),
            ),
        )
        assert response.status_code == 200, response.text
        observations_response = client.get("/v1/observations")
        assert observations_response.status_code == 200
        observations = [
            Observation.model_validate(item) for item in observations_response.json()
        ]

    assert len(observations) == 1
    assert len(build_hotspots_as_of(observations, as_of)) == 1
    # Correct server-side arrival time would exclude this late submission.
    corrected = observations[0].model_copy(update={"ingested_at": datetime.now(UTC)})
    assert build_hotspots_as_of([corrected], as_of) == []
