"""Deterministic policy output schema (SRD FR-06)."""

from typing import Literal
from pydantic import BaseModel, Field

from app.schemas.telemetry import FreshnessStatus

RiskCategory = Literal["low", "moderate", "high", "very_high", "severe", "unknown"]


class PolicyDecision(BaseModel):
    policyVersion: str
    aqiStandard: str
    riskCategory: RiskCategory
    freshnessStatus: FreshnessStatus
    flags: list[str] = Field(default_factory=list)
    allowedThemes: list[str] = Field(default_factory=list)
    prohibitedThemes: list[str] = Field(default_factory=list)
    profileModifiersApplied: list[str] = Field(default_factory=list)
    ventilationPermitted: bool
    strenuousOutdoorDiscouraged: bool
    conservativeGuidanceRequired: bool
    medicalDisclaimerRequired: bool
    aiGenerationAllowed: bool = True
