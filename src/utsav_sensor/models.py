from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class Provenance(StrEnum):
    VERIFIED_OFFICIAL = "verified_official"
    MEASURED = "measured"
    OBSERVED = "observed"
    MODELLED = "modelled"


class SourceType(StrEnum):
    CITIZEN = "citizen"
    PARTNER = "partner"
    OFFICIAL = "official"
    CCTV = "cctv"
    SATELLITE = "satellite"
    MODEL = "model"


class Observation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_type: SourceType
    provenance: Provenance
    source_id: str = Field(min_length=1, max_length=200)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = Field(default=0.5, ge=0, le=1)
    media_quality: float = Field(default=1.0, ge=0, le=1)
    materials: dict[str, float] = Field(default_factory=dict)
    mass_kg_low: float | None = Field(default=None, ge=0)
    mass_kg_high: float | None = Field(default=None, ge=0)
    status: str = Field(default="open", pattern="^(open|claimed|cleaning|cleaned|verified|candidate)$")
    external_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("materials")
    @classmethod
    def material_probs(cls, value: dict[str, float]) -> dict[str, float]:
        if any(v < 0 or v > 1 for v in value.values()):
            raise ValueError("material probabilities must be in [0, 1]")
        return value

    def model_post_init(self, __context: Any) -> None:
        if self.mass_kg_low is not None and self.mass_kg_high is not None:
            if self.mass_kg_low > self.mass_kg_high:
                raise ValueError("mass_kg_low cannot exceed mass_kg_high")


class HotspotState(BaseModel):
    id: str
    lat: float
    lon: float
    status: str
    observation_count: int
    independent_sources: int
    last_observed_at: datetime
    freshness: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    materials: dict[str, float]
    mass_kg_low: float | None = None
    mass_kg_high: float | None = None
    mass_basis: Provenance | None = None
    unresolved_hours: float = Field(ge=0)
    unresolved_waste_hours_low: float | None = None
    unresolved_waste_hours_high: float | None = None
    observation_ids: list[str]
