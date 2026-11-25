"""Server-side WAQI / AQICN adapter with allowlisted URLs, timeouts, and strict validation (SRD FR-04, §10.2)."""

from datetime import datetime, timezone
import os
from typing import Any, Optional
import requests

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

ALLOWLISTED_WAQI_HOST = "https://api.waqi.info/feed"


class ProviderError(Exception):
    """Structured error raised on provider timeout, quota, or malformed payload."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _safe_float(value: Any, min_val: float, max_val: float) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num < min_val or num > max_val:
        return None
    return round(num, 1)


def _parse_observed_timestamp(time_block: dict[str, Any], fallback_now: datetime) -> tuple[str, Optional[int]]:
    iso_raw = time_block.get("iso") or time_block.get("s")
    if isinstance(iso_raw, str) and iso_raw.strip():
        candidate = iso_raw.strip()
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            age = max(0, int((fallback_now - parsed.astimezone(timezone.utc)).total_seconds() // 60))
            return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), age
        except ValueError:
            pass
    return fallback_now.isoformat().replace("+00:00", "Z"), None


def normalize_waqi_payload(
    city: SupportedCityModel,
    payload: dict[str, Any],
    now: Optional[datetime] = None,
) -> EnvironmentalTelemetry:
    """Normalize and validate a WAQI JSON payload into EnvironmentalTelemetry."""
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        status_val = payload.get("status") if isinstance(payload, dict) else "invalid"
        data_msg = payload.get("data") if isinstance(payload, dict) else "Malformed payload"
        if isinstance(data_msg, str) and "quota" in data_msg.lower():
            raise ProviderError("provider_quota", "Environmental provider quota exceeded.")
        raise ProviderError("provider_malformed", f"Provider returned unusable status: {status_val}")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise ProviderError("provider_malformed", "Provider response missing data object.")

    city_block = data.get("city") or {}
    iaqi = data.get("iaqi") or {}
    time_block = data.get("time") or {}

    station_name = str(city_block.get("name") or f"{city.name} Monitoring Station").strip()
    station_id = str(data.get("idx") or city.waqi_query).strip()
    if not station_name or not station_id:
        raise ProviderError("no_station", "Station identity missing in provider response.")

    aqi = _safe_float(data.get("aqi"), 0.0, 1500.0)
    pm25 = _safe_float((iaqi.get("pm25") or {}).get("v"), 0.0, 2000.0)
    pm10 = _safe_float((iaqi.get("pm10") or {}).get("v"), 0.0, 3000.0)

    if aqi is None and pm25 is None and pm10 is None:
        raise ProviderError("no_station", "Provider returned no usable AQI, PM2.5, or PM10 values.")

    ref_now = now or datetime.now(timezone.utc)
    retrieved_iso = ref_now.isoformat().replace("+00:00", "Z")
    observed_iso, age_minutes = _parse_observed_timestamp(time_block, ref_now)

    source_url = str(city_block.get("url") or f"https://aqicn.org/city/{city.waqi_query}/")
    if not source_url.startswith("https://"):
        source_url = f"https://aqicn.org/city/{city.waqi_query}/"

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
            provider="WAQI / World Air Quality Index",
            url=source_url,
            retrievedAt=retrieved_iso,
            observedAt=observed_iso,
        ),
        freshness=TelemetryFreshness(
            status="unavailable" if age_minutes is None else "live",
            ageMinutes=age_minutes,
        ),
    )


def fetch_waqi_reading(city: SupportedCityModel, timeout_seconds: float = 6.0) -> EnvironmentalTelemetry:
    """Server-only live fetch from allowlisted WAQI endpoint with bounded timeout and 1 retry."""
    token = os.environ.get("WAQI_API_TOKEN", "").strip()
    if not token:
        raise ProviderError("provider_unconfigured", "WAQI_API_TOKEN is not configured on the server.")

    url = f"{ALLOWLISTED_WAQI_HOST}/{city.waqi_query}/"
    last_error: Optional[Exception] = None

    for attempt in range(2):
        try:
            resp = requests.get(url, params={"token": token}, timeout=timeout_seconds)
            if resp.status_code == 429:
                raise ProviderError("provider_quota", "WAQI API rate limit or quota exceeded.")
            if resp.status_code >= 500:
                raise ProviderError("provider_unavailable", f"WAQI upstream error ({resp.status_code}).")
            if resp.status_code != 200:
                raise ProviderError("provider_error", f"Unexpected WAQI HTTP status {resp.status_code}.")
            return normalize_waqi_payload(city, resp.json())
        except ProviderError as err:
            last_error = err
            if err.code in {"provider_quota", "provider_malformed", "no_station"} or attempt == 1:
                raise
        except requests.Timeout as exc:
            last_error = ProviderError("provider_timeout", "Environmental provider timed out.")
            if attempt == 1:
                raise last_error from exc
        except (requests.RequestException, ValueError) as exc:
            last_error = ProviderError("provider_error", "Failed to read environmental provider response.")
            if attempt == 1:
                raise last_error from exc

    raise last_error or ProviderError("provider_error", "Environmental provider failed.")
