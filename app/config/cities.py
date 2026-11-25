"""Allowlisted Indian cities and station mappings (SRD FR-01, §10.2)."""

from typing import TypedDict


class SupportedCity(TypedDict):
    id: str
    name: str
    region: str
    latitude: float
    longitude: float
    waqi_query: str
    aliases: list[str]


SUPPORTED_CITIES: list[SupportedCity] = [
    {
        "id": "delhi",
        "name": "Delhi",
        "region": "Delhi NCR",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "waqi_query": "delhi",
        "aliases": ["delhi", "new delhi", "delhi ncr", "ncr"],
    },
    {
        "id": "noida",
        "name": "Noida",
        "region": "Uttar Pradesh (NCR)",
        "latitude": 28.5355,
        "longitude": 77.3910,
        "waqi_query": "noida",
        "aliases": ["noida", "greater noida", "sector 62 noida"],
    },
    {
        "id": "mumbai",
        "name": "Mumbai",
        "region": "Maharashtra",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "waqi_query": "mumbai",
        "aliases": ["mumbai", "bombay", "bandra", "worli"],
    },
    {
        "id": "kolkata",
        "name": "Kolkata",
        "region": "West Bengal",
        "latitude": 22.5726,
        "longitude": 88.3639,
        "waqi_query": "kolkata",
        "aliases": ["kolkata", "calcutta", "ballygunge"],
    },
]
