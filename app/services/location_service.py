"""Allowlisted location resolution and station mapping service (SRD FR-01, §9.3, §10.2)."""

import math
from typing import Optional

from app.config.cities import SUPPORTED_CITIES
from app.schemas.location import LocationResolutionResponse, SupportedCityModel


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return 2.0 * r * math.asin(math.sqrt(a))


def get_allowlisted_city(location_id: str) -> Optional[SupportedCityModel]:
    normalized = (location_id or "").strip().lower()
    for city in SUPPORTED_CITIES:
        if city["id"] == normalized:
            return SupportedCityModel(**city)
    return None


def search_locations(
    query: str = "",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> LocationResolutionResponse:
    cleaned = (query or "").strip().lower()

    if lat is not None and lon is not None:
        nearest = None
        min_dist = float("inf")
        for city in SUPPORTED_CITIES:
            dist = _haversine_km(lat, lon, city["latitude"], city["longitude"])
            if dist < min_dist:
                min_dist = dist
                nearest = city
        if nearest and min_dist <= 80.0:
            model = SupportedCityModel(**nearest)
            return LocationResolutionResponse(
                resolutionStatus="matched",
                query=f"{lat:.4f},{lon:.4f}",
                matches=[model],
                message=f"Matched nearest supported city: {model.name} ({round(min_dist)} km).",
            )
        return LocationResolutionResponse(
            resolutionStatus="unsupported",
            query=f"{lat:.4f},{lon:.4f}",
            matches=[],
            message="Coordinates are outside the supported Indian cities (Delhi, Noida, Mumbai, Kolkata).",
        )

    if not cleaned:
        models = [SupportedCityModel(**c) for c in SUPPORTED_CITIES]
        return LocationResolutionResponse(
            resolutionStatus="matched",
            query="",
            matches=models,
            message="Showing all supported cities.",
        )

    matches: list[SupportedCityModel] = []
    for city in SUPPORTED_CITIES:
        haystack = [city["id"], city["name"].lower(), city["region"].lower(), *city["aliases"]]
        if any(cleaned in item for item in haystack):
            matches.append(SupportedCityModel(**city))

    if len(matches) == 1:
        return LocationResolutionResponse(
            resolutionStatus="matched",
            query=query,
            matches=matches,
            message=f"Matched {matches[0].name}.",
        )
    if len(matches) > 1:
        return LocationResolutionResponse(
            resolutionStatus="ambiguous",
            query=query,
            matches=matches,
            message="Multiple supported locations match your search. Choose a specific city.",
        )
    return LocationResolutionResponse(
        resolutionStatus="unsupported",
        query=query,
        matches=[],
        message=f'"{query}" is outside the initial supported cities (Delhi, Noida, Mumbai, Kolkata).',
    )
