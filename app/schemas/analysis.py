"""API request and response contracts for POST /api/analysis (SRD §9.5)."""

from typing import Literal, Optional
from pydantic import BaseModel, Field

from app.schemas.plan import GroundedPlan
from app.schemas.policy import PolicyDecision
from app.schemas.profile import UserProfile
from app.schemas.telemetry import EnvironmentalTelemetry


class AnalysisOptions(BaseModel):
    language: Literal["en"] = "en"
    includeHourlyPlan: bool = True
    forceRefresh: bool = False
    simulateMode: Optional[
        Literal[
            "normal",
            "stale",
            "partial_pm",
            "provider_timeout",
            "provider_quota",
            "no_station",
            "ai_timeout",
            "ai_invalid_json",
            "ai_unavailable",
        ]
    ] = None


class AnalysisRequest(BaseModel):
    locationId: str = Field(min_length=1, max_length=40)
    profile: UserProfile
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)


class ProvenanceInfo(BaseModel):
    provider: str
    sourceUrl: str
    observedAt: str
    retrievedAt: str
    analysisVersion: str
    policyVersion: str
    promptVersion: str


class AnalysisResponse(BaseModel):
    requestId: str
    status: Literal["success", "degraded", "unavailable"]
    telemetry: EnvironmentalTelemetry
    policy: PolicyDecision
    plan: GroundedPlan
    provenance: ProvenanceInfo
    limitations: list[str] = Field(default_factory=list)
    degradedMode: bool = False
    degradedReason: Optional[str] = None
