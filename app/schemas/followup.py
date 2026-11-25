"""Grounded conversational follow-up schemas (SRD §6.1, §8.8)."""

from pydantic import BaseModel, Field

from app.schemas.plan import GroundedPlan
from app.schemas.policy import PolicyDecision
from app.schemas.profile import UserProfile
from app.schemas.telemetry import EnvironmentalTelemetry


class FollowupRequest(BaseModel):
    question: str = Field(min_length=2, max_length=320)
    telemetry: EnvironmentalTelemetry
    policy: PolicyDecision
    profile: UserProfile
    plan: GroundedPlan


class FollowupResponse(BaseModel):
    answer: str
    nextStep: str
    degradedMode: bool = False
