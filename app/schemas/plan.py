"""Structured AI Plan JSON schema matching SRD §8.5 and FR-08."""

from typing import Literal
from pydantic import BaseModel, Field

RiskLevel = Literal["low", "moderate", "high", "very_high", "severe", "unknown"]
ActionPriority = Literal["must_do", "recommended", "optional"]
PeriodName = Literal["morning", "afternoon", "evening", "night"]
ConfidenceLevel = Literal["high", "medium", "low"]


class PrioritySummary(BaseModel):
    level: RiskLevel
    title: str = Field(min_length=3, max_length=140)
    action: str = Field(min_length=5, max_length=300)
    reason: str = Field(min_length=5, max_length=300)


class TimelineAction(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    condition: str = Field(min_length=3, max_length=240)
    action: str = Field(min_length=3, max_length=260)
    reason: str = Field(min_length=3, max_length=260)
    benefit: str = Field(min_length=3, max_length=240)
    tradeoff: str = Field(min_length=2, max_length=240)
    priority: ActionPriority


class TimelinePeriod(BaseModel):
    period: PeriodName
    window: str = Field(min_length=3, max_length=40)
    risk: RiskLevel
    recommendation: str = Field(min_length=5, max_length=320)
    actions: list[TimelineAction] = Field(min_length=1, max_length=4)
    indoorAlternative: str = Field(min_length=3, max_length=260)


class IndoorAirItem(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    action: str = Field(min_length=3, max_length=260)
    reason: str = Field(min_length=3, max_length=260)
    when: str = Field(min_length=2, max_length=120)
    caution: str = Field(min_length=2, max_length=240)


class MobilityOption(BaseModel):
    option: str = Field(min_length=3, max_length=120)
    bestFor: str = Field(min_length=3, max_length=180)
    whyItHelps: str = Field(min_length=3, max_length=260)
    tradeoff: str = Field(min_length=2, max_length=220)


class ConfidenceInfo(BaseModel):
    level: ConfidenceLevel
    reason: str = Field(min_length=5, max_length=280)


class GroundedPlan(BaseModel):
    analysisVersion: str = "1.0"
    headline: str = Field(min_length=5, max_length=220)
    priority: PrioritySummary
    timeline: list[TimelinePeriod] = Field(min_length=4, max_length=4)
    indoorAirPlan: list[IndoorAirItem] = Field(min_length=1, max_length=5)
    mobilityOptions: list[MobilityOption] = Field(min_length=1, max_length=5)
    profileDrivers: list[str] = Field(min_length=1, max_length=8)
    limitations: list[str] = Field(min_length=1, max_length=8)
    safetyNote: str = Field(min_length=10, max_length=400)
    confidence: ConfidenceInfo
