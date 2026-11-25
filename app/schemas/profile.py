"""User profile schema with minimal required fields and optional sensitive health flags (SRD FR-02, §10.3)."""

from typing import Literal, Optional
from pydantic import BaseModel, Field

HouseholdMember = Literal["adult", "child", "senior", "pregnant"]
VulnerabilityFlag = Literal["respiratory_condition", "cardiovascular_condition"]
PrimaryActivity = Literal["commute", "school", "sports", "errands", "outdoor_work"]
CommuteMode = Literal["walking", "two_wheeler", "car", "public_transit", "carpool", "mixed"]
CommuteTime = Literal["morning", "afternoon", "evening", "flexible"]
TimePeriod = Literal["morning", "afternoon", "evening", "night"]


class IndoorContext(BaseModel):
    purifierAvailable: bool = False
    indoorSensorAvailable: bool = False
    cookingExposure: bool = False
    ventilationConstraints: bool = False


class PlannedOutdoorActivity(BaseModel):
    activity: str = Field(min_length=1, max_length=80)
    preferredPeriod: TimePeriod = "morning"


class UserProfile(BaseModel):
    household: list[HouseholdMember] = Field(min_length=1, max_length=10)
    vulnerabilities: list[VulnerabilityFlag] = Field(default_factory=list, max_length=5)
    primaryActivities: list[PrimaryActivity] = Field(min_length=1, max_length=5)
    commuteMode: CommuteMode
    commuteTime: CommuteTime = "morning"
    outdoorWorkerOrAthlete: bool = False
    indoorContext: IndoorContext = Field(default_factory=IndoorContext)
    plannedOutdoorActivity: Optional[PlannedOutdoorActivity] = None
    priorities: list[str] = Field(default_factory=list, max_length=6)
    isSamplePreset: bool = False
    presetId: Optional[str] = Field(default=None, max_length=60)
    presetLabel: Optional[str] = Field(default=None, max_length=100)
