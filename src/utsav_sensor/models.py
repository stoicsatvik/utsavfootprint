from __future__ import annotations

import math
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator


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
    observed_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    ingested_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))

    confidence: float = Field(default=0.5, ge=0, le=1)
    media_quality: float = Field(default=1.0, ge=0, le=1)
    materials: dict[str, float] = Field(default_factory=dict)
    mass_kg_low: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    mass_kg_high: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    status: str = Field(default="open", pattern="^(open|claimed|cleaning|cleaned|verified|candidate)$")
    external_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("observed_at", "ingested_at")
    @classmethod
    def canonicalize_utc(cls, value: datetime) -> datetime:
        # AwareDatetime rejects ambiguous naive input before this validator.
        # Canonical UTC matches the earlier E175 contract and keeps stored
        # timestamps comparable even when producers use different offsets.
        return value.astimezone(UTC)

    @field_validator("materials")
    @classmethod
    def material_probs(cls, value: dict[str, float]) -> dict[str, float]:
        if any(not math.isfinite(v) or v < 0 or v > 1 for v in value.values()):
            raise ValueError("material probabilities must be finite and in [0, 1]")
        return value

    @model_validator(mode="after")
    def valid_mass_range(self):
        if (
            self.mass_kg_low is not None
            and self.mass_kg_high is not None
            and self.mass_kg_low > self.mass_kg_high
        ):
            raise ValueError("mass_kg_low cannot exceed mass_kg_high")
        return self


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
    # Reject non-finite/negative fused output even for callers bypassing Observation.
    mass_kg_low: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    mass_kg_high: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    mass_basis: Provenance | None = None
    unresolved_hours: float = Field(ge=0, allow_inf_nan=False)
    unresolved_waste_hours_low: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    unresolved_waste_hours_high: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    # True means at least one derived mass-hour product overflowed, not missing evidence.
    unresolved_waste_hours_overflow: bool = False
    # None denotes a legacy state without per-bound diagnostics. Explicit
    # booleans let metrics distinguish an absent bound from arithmetic overflow.
    unresolved_waste_hours_overflow_low: bool | None = None
    unresolved_waste_hours_overflow_high: bool | None = None
    observation_ids: list[str]

    @model_validator(mode="after")
    def valid_mass_hour_overflow_flags(self):
        if (
            self.mass_kg_low is not None
            and self.mass_kg_high is not None
            and self.mass_kg_low > self.mass_kg_high
        ):
            raise ValueError("mass_kg_low cannot exceed mass_kg_high")
        bounds = (
            (self.unresolved_waste_hours_low, self.unresolved_waste_hours_overflow_low),
            (self.unresolved_waste_hours_high, self.unresolved_waste_hours_overflow_high),
        )
        if any(flag is True and value is not None for value, flag in bounds):
            raise ValueError("an overflowed mass-hour bound must have a null value")
        if any(flag is True for _, flag in bounds) and not self.unresolved_waste_hours_overflow:
            raise ValueError("aggregate mass-hour overflow must include each flagged bound")
        if all(flag is not None for _, flag in bounds) and (
            self.unresolved_waste_hours_overflow != any(flag for _, flag in bounds)
        ):
            raise ValueError("aggregate mass-hour overflow disagrees with known bound flags")
        return self


class SourceHealth(BaseModel):
    source_id: str
    source_type: SourceType
    last_ingested_at: datetime
    observation_count: int
    age_seconds: float = Field(ge=0)
    state: str
