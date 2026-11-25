"""Normalized environmental telemetry schema (SRD FR-04, FR-05)."""

from typing import Literal, Optional
from pydantic import BaseModel, Field

FreshnessStatus = Literal["live", "recent", "stale", "unavailable"]


class TelemetryLocation(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    city: str = Field(min_length=1, max_length=80)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)


class TelemetryStation(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    id: str = Field(min_length=1, max_length=100)


class TelemetryMeasurements(BaseModel):
    aqi: Optional[float] = Field(default=None, ge=0.0, le=1500.0)
    pm25: Optional[float] = Field(default=None, ge=0.0, le=2000.0)
    pm10: Optional[float] = Field(default=None, ge=0.0, le=3000.0)
    unit: Literal["µg/m³"] = "µg/m³"
    aqiStandard: str = "US-EPA (WAQI)"


class TelemetrySource(BaseModel):
    provider: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=300)
    retrievedAt: str = Field(min_length=1, max_length=64)
    observedAt: str = Field(min_length=1, max_length=64)


class TelemetryFreshness(BaseModel):
    status: FreshnessStatus
    ageMinutes: Optional[int] = Field(default=None, ge=0)


class EnvironmentalTelemetry(BaseModel):
    location: TelemetryLocation
    station: TelemetryStation
    measurements: TelemetryMeasurements
    source: TelemetrySource
    freshness: TelemetryFreshness
