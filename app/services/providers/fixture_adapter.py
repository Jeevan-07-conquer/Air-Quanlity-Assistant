"""Labeled deterministic telemetry fixtures for local evaluation and automated tests (SRD Prompt 04)."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config.policy_thresholds import AQI_STANDARD
from app.schemas.location import SupportedCityModel
from app.schemas.telemetry import (
    EnvironmentalTelemetry,
    TelemetryFreshness,
    TelemetryLocation,
    TelemetryMeasurements,
    TelemetrySource,
    TelemetryStation,
)

# Baseline realistic scenarios per allowlisted city (clearly labeled as deterministic fixtures)
CITY_FIXTURES: dict[str, dict] = {
    "delhi": {
        "station_name": "Anand Vihar, Delhi - DPCC (Fixture)",
        "station_id": "fixture-dl-anand-vihar",
        "aqi": 318.0,
        "pm25": 168.4,
        "pm10": 292.0,
        "age_minutes": 18,
    },
    "noida": {
        "station_name": "Sector 62, Noida - IMD (Fixture)",
        "station_id": "fixture-up-noida-s62",
        "aqi": 244.0,
        "pm25": 119.5,
        "pm10": 215.2,
        "age_minutes": 24,
    },
    "mumbai": {
        "station_name": "Bandra Kurla Complex, Mumbai - MPCB (Fixture)",
        "station_id": "fixture-mh-mumbai-bkc",
        "aqi": 134.0,
        "pm25": 49.2,
        "pm10": 108.6,
        "age_minutes": 42,
    },
    "kolkata": {
        "station_name": "Ballygunge, Kolkata - WBPCB (Fixture)",
        "station_id": "fixture-wb-kolkata-ballygunge",
        "aqi": 162.0,
        "pm25": 68.0,
        "pm10": 136.4,
        "age_minutes": 20,
    },
}


def build_fixture_telemetry(
    city: SupportedCityModel,
    simulate_mode: Optional[str] = None,
    now: Optional[datetime] = None,
) -> EnvironmentalTelemetry:
    """Return a strictly schema-valid, clearly labeled fixture reading."""
    ref_now = now or datetime.now(timezone.utc)
    base = CITY_FIXTURES.get(city.id, CITY_FIXTURES["delhi"])

    age_minutes = base["age_minutes"]
    aqi: Optional[float] = base["aqi"]
    pm25: Optional[float] = base["pm25"]
    pm10: Optional[float] = base["pm10"]
    station_name = base["station_name"]
    station_id = base["station_id"]

    if simulate_mode == "stale":
        age_minutes = 195
    elif simulate_mode == "partial_pm":
        pm10 = None
    elif simulate_mode == "no_station":
        aqi = None
        pm25 = None
        pm10 = None
        station_name = "No active station data available"
        station_id = "unavailable"
        age_minutes = None

    retrieved_iso = ref_now.isoformat().replace("+00:00", "Z")
    if age_minutes is not None:
        observed_iso = (ref_now - timedelta(minutes=age_minutes)).isoformat().replace("+00:00", "Z")
    else:
        observed_iso = retrieved_iso

    return EnvironmentalTelemetry(
        location=TelemetryLocation(
            id=city.id,
            city=city.name,
            latitude=city.latitude,
            longitude=city.longitude,
        ),
        station=TelemetryStation(name=station_name, id=station_id),
        measurements=TelemetryMeasurements(
            aqi=aqi,
            pm25=pm25,
            pm10=pm10,
            unit="µg/m³",
            aqiStandard=AQI_STANDARD,
        ),
        source=TelemetrySource(
            provider="Deterministic Evaluation Fixture (Simulated Provider)",
            url="https://aqicn.org/city/india/",
            retrievedAt=retrieved_iso,
            observedAt=observed_iso,
        ),
        freshness=TelemetryFreshness(
            status="unavailable" if age_minutes is None else "live",
            ageMinutes=age_minutes,
        ),
    )
