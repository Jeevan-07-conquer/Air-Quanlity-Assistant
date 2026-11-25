"""Location and station resolution schemas (SRD FR-01, §9.5)."""

from typing import Literal
from pydantic import BaseModel, Field


class SupportedCityModel(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    region: str = Field(min_length=1, max_length=100)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    waqi_query: str = Field(min_length=1, max_length=80)
    aliases: list[str] = Field(default_factory=list)


class LocationResolutionResponse(BaseModel):
    resolutionStatus: Literal["matched", "ambiguous", "unsupported"]
    query: str
    matches: list[SupportedCityModel] = Field(default_factory=list)
    message: str
