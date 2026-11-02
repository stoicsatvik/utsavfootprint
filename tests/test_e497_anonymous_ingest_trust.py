"""E497: anonymous POST cannot self-certify privileged observation evidence."""
import pytest
from fastapi.testclient import TestClient

from utsav_sensor import api


def payload(**overrides):
    result = {
        "id": "e497-synthetic-claim",
        "source_type": "citizen",
        "provenance": "observed",
        "source_id": "anonymous-claim",
        "lat": 19.076,
        "lon": 72.8777,
        "status": "open",
    }
    result.update(overrides)
    return result


@pytest.mark.parametrize(
    "override",
    [
        {"source_type": "official"},
        {"source_type": "partner"},
        {"source_type": "cctv"},
        {"source_type": "satellite"},
        {"source_type": "model"},
        {"provenance": "verified_official"},
        {"provenance": "measured"},
        {"provenance": "modelled"},
        {"status": "verified"},
        {"status": "cleaned"},
        {"status": "claimed"},
        {"status": "cleaning"},
    ],
)
def test_anonymous_privileged_claim_rejected_before_ingest(monkeypatch, override):
    calls = []

    async def spy(observation):
        calls.append(observation)
        return observation

    monkeypatch.setattr(api.engine, "ingest", spy)
    response = TestClient(api.app).post("/v1/observations", json=payload(**override))
    assert response.status_code == 403
    assert response.json()["detail"] == (
        "anonymous observations may only be citizen/observed/open-or-candidate"
    )
    assert calls == []


@pytest.mark.parametrize("status", ["open", "candidate"])
def test_unprivileged_anonymous_observation_still_accepted(monkeypatch, status):
    calls = []

    async def spy(observation):
        calls.append(observation)
        return observation

    monkeypatch.setattr(api.engine, "ingest", spy)
    response = TestClient(api.app).post("/v1/observations", json=payload(status=status))
    assert response.status_code == 200
    assert len(calls) == 1
    assert response.json()["status"] == status


def test_negative_anonymous_source_id_and_confidence_remain_unverified(monkeypatch):
    """Passing the gate does not authenticate a claimed source or confidence."""
    calls = []

    async def spy(observation):
        calls.append(observation)
        return observation

    monkeypatch.setattr(api.engine, "ingest", spy)
    response = TestClient(api.app).post(
        "/v1/observations",
        json=payload(source_id="claimed-government-department", confidence=1.0),
    )
    assert response.status_code == 200
    assert calls[0].source_id == "claimed-government-department"
    assert calls[0].confidence == 1.0


def test_negative_client_ingestion_timestamp_still_accepted(monkeypatch):
    """Server-side timestamp issuance remains a separate, unresolved boundary."""
    calls = []

    async def spy(observation):
        calls.append(observation)
        return observation

    monkeypatch.setattr(api.engine, "ingest", spy)
    response = TestClient(api.app).post(
        "/v1/observations",
        json=payload(ingested_at="2020-01-01T00:00:00+00:00"),
    )
    assert response.status_code == 200
    assert calls[0].ingested_at.year == 2020
