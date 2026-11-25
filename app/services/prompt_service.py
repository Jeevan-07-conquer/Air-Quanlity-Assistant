"""Prompt orchestrator enforcing evidence boundaries and exact metric preservation (SRD §8.2, Prompt 06)."""

from dataclasses import dataclass
from typing import Optional

from app.prompts.templates import (
    PROMPT_VERSION,
    REPAIR_PROMPT_TEMPLATE_V1,
    SYSTEM_PROMPT_V1,
    USER_PROMPT_TEMPLATE_V1,
)
from app.schemas.policy import PolicyDecision
from app.schemas.profile import UserProfile
from app.schemas.telemetry import EnvironmentalTelemetry


@dataclass(frozen=True)
class PromptPayload:
    prompt_version: str
    policy_version: str
    request_id: str
    model_name: str
    token_budget: int
    system_prompt: str
    user_prompt: str


def _fmt_metric(value: Optional[float]) -> str:
    if value is None:
        return "unavailable"
    if value.is_integer():
        return str(int(value))
    return str(value)


def build_grounded_prompt(
    telemetry: EnvironmentalTelemetry,
    policy: PolicyDecision,
    profile: UserProfile,
    request_id: str,
    model_name: str = "gemini-3.8-flash",
    token_budget: int = 4096,
) -> PromptPayload:
    """Assemble compact, redacted, strictly grounded system + user prompts."""
    planned = list(profile.primaryActivities)
    if profile.plannedOutdoorActivity:
        planned.append(
            f"{profile.plannedOutdoorActivity.activity} ({profile.plannedOutdoorActivity.preferredPeriod})"
        )

    vulnerable_summary = (
        ", ".join(profile.vulnerabilities) if profile.vulnerabilities else "none_specified"
    )
    if any(m in {"child", "senior", "pregnant"} for m in profile.household):
        age_groups = [m for m in profile.household if m in {"child", "senior", "pregnant"}]
        vulnerable_summary = f"{vulnerable_summary}; household_groups: {', '.join(age_groups)}"

    user_prompt = USER_PROMPT_TEMPLATE_V1.format(
        city=telemetry.location.city,
        station_name=telemetry.station.name,
        provider=telemetry.source.provider,
        provider_url=telemetry.source.url,
        aqi=_fmt_metric(telemetry.measurements.aqi),
        pm25=_fmt_metric(telemetry.measurements.pm25),
        pm10=_fmt_metric(telemetry.measurements.pm10),
        unit=telemetry.measurements.unit,
        aqi_standard=telemetry.measurements.aqiStandard,
        observed_at=telemetry.source.observedAt,
        retrieved_at=telemetry.source.retrievedAt,
        freshness_status=telemetry.freshness.status,
        age_minutes=str(telemetry.freshness.ageMinutes)
        if telemetry.freshness.ageMinutes is not None
        else "unavailable",
        risk_category=policy.riskCategory,
        policy_flags=", ".join(policy.flags) if policy.flags else "none",
        prohibited_themes=", ".join(policy.prohibitedThemes),
        household_members=", ".join(profile.household),
        vulnerable_groups=vulnerable_summary,
        commute_mode=profile.commuteMode,
        commute_time=profile.commuteTime,
        planned_activities=", ".join(planned),
        outdoor_worker_or_athlete=str(profile.outdoorWorkerOrAthlete).lower(),
        indoor_purifier_available=str(profile.indoorContext.purifierAvailable).lower(),
        indoor_sensor_available=str(profile.indoorContext.indoorSensorAvailable).lower(),
        cooking_exposure=str(profile.indoorContext.cookingExposure).lower(),
        ventilation_constraints=str(profile.indoorContext.ventilationConstraints).lower(),
        priorities=", ".join(profile.priorities) if profile.priorities else "general exposure safety",
    )

    return PromptPayload(
        prompt_version=PROMPT_VERSION,
        policy_version=policy.policyVersion,
        request_id=request_id,
        model_name=model_name,
        token_budget=token_budget,
        system_prompt=SYSTEM_PROMPT_V1,
        user_prompt=user_prompt,
    )


def build_repair_prompt(validation_error: str) -> str:
    return REPAIR_PROMPT_TEMPLATE_V1.format(validation_error=validation_error)
