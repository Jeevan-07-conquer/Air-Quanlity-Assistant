"""Provider-neutral environmental telemetry service with freshness classification & caching (SRD FR-04, FR-05, §9.6)."""

from datetime import datetime, timezone
import os
import time
from typing import Optional

from app.config.policy_thresholds import (
    AQI_STANDARD,
    LIVE_MAX_MINUTES,
    RECENT_MAX_MINUTES,
    STALE_MAX_MINUTES,
    TELEMETRY_CACHE_TTL_SECONDS,
)
from app.schemas.location import SupportedCityModel
from app.schemas.telemetry import (
    EnvironmentalTelemetry,
    FreshnessStatus,
    TelemetryFreshness,
    TelemetryLocation,
    TelemetryMeasurements,
    TelemetrySource,
    TelemetryStation,
)
from app.services.providers.fixture_adapter import build_fixture_telemetry
from app.services.providers.waqi_adapter import ProviderError, fetch_waqi_reading

# Cache keyed by (location_id, mode) — never by user profile (SRD §9.6)
_TELEMETRY_CACHE: dict[str, tuple[float, EnvironmentalTelemetry]] = {}
_LAST_GOOD_TELEMETRY: dict[str, EnvironmentalTelemetry] = {}


def clear_telemetry_cache() -> None:
    _TELEMETRY_CACHE.clear()
    _LAST_GOOD_TELEMETRY.clear()


def classify_freshness(telemetry: EnvironmentalTelemetry) -> FreshnessStatus:
    """Determine live / recent / stale / unavailable deterministically (FR-05)."""
    m = telemetry.measurements
    if m.aqi is None and m.pm25 is None and m.pm10 is None:
        return "unavailable"

    age = telemetry.freshness.ageMinutes
    if age is None or age < 0:
        return "unavailable"
    if age <= LIVE_MAX_MINUTES:
        return "live"
    if age <= RECENT_MAX_MINUTES:
        return "recent"
    if age <= STALE_MAX_MINUTES:
        return "stale"
    return "unavailable"


def with_classified_freshness(telemetry: EnvironmentalTelemetry) -> EnvironmentalTelemetry:
    status = classify_freshness(telemetry)
    return telemetry.model_copy(
        update={
            "freshness": TelemetryFreshness(
                status=status,
                ageMinutes=telemetry.freshness.ageMinutes,
            )
        }
    )


def build_unavailable_telemetry(city: SupportedCityModel, reason: str) -> EnvironmentalTelemetry:
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return EnvironmentalTelemetry(
        location=TelemetryLocation(
            id=city.id,
            city=city.name,
            latitude=city.latitude,
            longitude=city.longitude,
        ),
        station=TelemetryStation(name="Unavailable", id="unavailable"),
        measurements=TelemetryMeasurements(
            aqi=None,
            pm25=None,
            pm10=None,
            unit="µg/m³",
            aqiStandard=AQI_STANDARD,
        ),
        source=TelemetrySource(
            provider=f"Unavailable ({reason})",
            url="https://aqicn.org/city/india/",
            retrievedAt=now_iso,
            observedAt=now_iso,
        ),
        freshness=TelemetryFreshness(status="unavailable", ageMinutes=None),
    )


def get_latest_reading(
    city: SupportedCityModel,
    simulate_mode: Optional[str] = None,
    force_refresh: bool = False,
) -> tuple[EnvironmentalTelemetry, Optional[str]]:
    """Retrieve, validate, classify freshness, and cache environmental telemetry.

    Returns (telemetry, provider_issue_code). Never fabricates readings on provider failure.
    """
    if simulate_mode == "provider_timeout":
        cached = _LAST_GOOD_TELEMETRY.get(city.id)
        if cached:
            stale_copy = cached.model_copy(
                update={
                    "freshness": TelemetryFreshness(
                        status="stale",
                        ageMinutes=max(RECENT_MAX_MINUTES + 15, cached.freshness.ageMinutes or 150),
                    )
                }
            )
            return stale_copy, "provider_timeout"
        return build_unavailable_telemetry(city, "Provider timeout"), "provider_timeout"

    if simulate_mode == "provider_quota":
        return build_unavailable_telemetry(city, "Provider quota exceeded"), "provider_quota"

    mode = os.environ.get("TELEMETRY_MODE", "fixture").strip().lower()
    use_live = mode == "live" and bool(os.environ.get("WAQI_API_TOKEN", "").strip()) and simulate_mode in (None, "normal")

    cache_key = f"{city.id}:{'live' if use_live else (simulate_mode or 'fixture')}"
    now_mono = time.monotonic()

    if not force_refresh and cache_key in _TELEMETRY_CACHE:
        expires_at, cached_telemetry = _TELEMETRY_CACHE[cache_key]
        if now_mono < expires_at:
            return cached_telemetry, None

    if use_live:
        try:
            timeout_s = max(1.0, float(os.environ.get("PROVIDER_TIMEOUT_MS", "6000")) / 1000.0)
            raw = fetch_waqi_reading(city, timeout_seconds=timeout_s)
            classified = with_classified_freshness(raw)
            _TELEMETRY_CACHE[cache_key] = (now_mono + TELEMETRY_CACHE_TTL_SECONDS, classified)
            if classified.freshness.status != "unavailable":
                _LAST_GOOD_TELEMETRY[city.id] = classified
            return classified, None
        except ProviderError as err:
            cached = _LAST_GOOD_TELEMETRY.get(city.id)
            if cached:
                stale_copy = cached.model_copy(
                    update={
                        "freshness": TelemetryFreshness(
                            status="stale",
                            ageMinutes=max(RECENT_MAX_MINUTES + 15, cached.freshness.ageMinutes or 150),
                        )
                    }
                )
                return stale_copy, err.code
            return build_unavailable_telemetry(city, err.message), err.code

    fixture = with_classified_freshness(build_fixture_telemetry(city, simulate_mode=simulate_mode))
    _TELEMETRY_CACHE[cache_key] = (now_mono + TELEMETRY_CACHE_TTL_SECONDS, fixture)
    if fixture.freshness.status != "unavailable":
        _LAST_GOOD_TELEMETRY[city.id] = fixture
    issue = "no_station" if fixture.freshness.status == "unavailable" else None
    return fixture, issue
