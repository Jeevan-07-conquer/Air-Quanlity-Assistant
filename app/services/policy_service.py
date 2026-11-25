"""Versioned deterministic policy engine running before any LLM call (SRD FR-06, Prompt 05)."""

from app.config.policy_thresholds import (
    AQI_STANDARD,
    AQI_THRESHOLDS,
    PM25_THRESHOLDS,
    POLICY_VERSION,
)
from app.schemas.policy import PolicyDecision, RiskCategory
from app.schemas.profile import UserProfile
from app.schemas.telemetry import EnvironmentalTelemetry

RISK_ORDER = ["unknown", "low", "moderate", "high", "very_high", "severe"]


def _escalate_risk(current: RiskCategory, minimum: RiskCategory) -> RiskCategory:
    if RISK_ORDER.index(minimum) > RISK_ORDER.index(current):
        return minimum
    return current


def _classify_base_risk(telemetry: EnvironmentalTelemetry) -> RiskCategory:
    m = telemetry.measurements
    risk: RiskCategory = "unknown"

    if m.aqi is not None:
        if m.aqi <= AQI_THRESHOLDS["low"]:
            risk = "low"
        elif m.aqi <= AQI_THRESHOLDS["moderate"]:
            risk = "moderate"
        elif m.aqi <= AQI_THRESHOLDS["high"]:
            risk = "high"
        elif m.aqi <= AQI_THRESHOLDS["very_high"]:
            risk = "very_high"
        else:
            risk = "severe"

    if m.pm25 is not None:
        pm_risk: RiskCategory
        if m.pm25 <= PM25_THRESHOLDS["low"]:
            pm_risk = "low"
        elif m.pm25 <= PM25_THRESHOLDS["moderate"]:
            pm_risk = "moderate"
        elif m.pm25 <= PM25_THRESHOLDS["high"]:
            pm_risk = "high"
        elif m.pm25 <= PM25_THRESHOLDS["very_high"]:
            pm_risk = "very_high"
        else:
            pm_risk = "severe"
        risk = _escalate_risk(risk, pm_risk)

    return risk


def evaluate_policy(telemetry: EnvironmentalTelemetry, profile: UserProfile) -> PolicyDecision:
    """Apply deterministic safety rules and profile modifiers prior to LLM generation."""
    freshness = telemetry.freshness.status
    flags: list[str] = []
    modifiers: list[str] = []
    allowed_themes: list[str] = [
        "time_window_shifting",
        "indoor_source_control",
        "commute_exposure_reduction",
        "clear_uncertainty_disclosure",
    ]
    prohibited_themes: list[str] = [
        "medical_diagnosis",
        "medication_prescription",
        "guaranteed_protection_claims",
        "fabricated_measurements",
    ]

    if freshness == "unavailable":
        flags.extend(["ai_generation_blocked", "conservative_guidance_required", "medical_disclaimer_required"])
        prohibited_themes.append("location_specific_current_air_advice")
        return PolicyDecision(
            policyVersion=POLICY_VERSION,
            aqiStandard=telemetry.measurements.aqiStandard or AQI_STANDARD,
            riskCategory="unknown",
            freshnessStatus="unavailable",
            flags=flags,
            allowedThemes=["provider_retry_guidance", "generic_precaution_only"],
            prohibitedThemes=prohibited_themes,
            profileModifiersApplied=["Telemetry unavailable: location-specific AI advice blocked."],
            ventilationPermitted=False,
            strenuousOutdoorDiscouraged=True,
            conservativeGuidanceRequired=True,
            medicalDisclaimerRequired=True,
            aiGenerationAllowed=False,
        )

    base_risk = _classify_base_risk(telemetry)
    effective_risk = base_risk

    has_vulnerable_member = any(m in {"child", "senior", "pregnant"} for m in profile.household)
    has_health_vulnerability = len(profile.vulnerabilities) > 0
    is_vulnerable = has_vulnerable_member or has_health_vulnerability

    if has_vulnerable_member:
        modifiers.append("Household includes child, senior, or pregnant member: conservative thresholds applied.")
    if has_health_vulnerability:
        modifiers.append("Health sensitivity indicated: heightened outdoor & indoor air caution applied.")
    if profile.outdoorWorkerOrAthlete:
        modifiers.append("Outdoor athlete/worker exertion multiplier: strenuous window restrictions tightened.")

    # Escalate effective guidance sensitivity for vulnerable households on moderate/high days
    if is_vulnerable and effective_risk == "moderate":
        effective_risk = "high"
        modifiers.append("Effective risk raised from moderate to high due to household vulnerability.")

    if freshness == "stale":
        flags.append("stale_data_caution")
        modifiers.append(
            f"Reading is stale ({telemetry.freshness.ageMinutes} min old): conservative caution applied."
        )

    strenuous_discouraged = effective_risk in {"high", "very_high", "severe"} or (
        profile.outdoorWorkerOrAthlete and effective_risk in {"moderate", "high", "very_high", "severe"}
    )
    if strenuous_discouraged:
        flags.append("discourage_strenuous_outdoor_activity")

    conservative_required = is_vulnerable or freshness == "stale" or effective_risk in {"very_high", "severe"}
    if conservative_required:
        flags.append("conservative_guidance_required")

    ventilation_permitted = effective_risk in {"low", "moderate"} and not profile.indoorContext.ventilationConstraints
    if not ventilation_permitted:
        flags.append("ventilation_prohibited")
        prohibited_themes.append("recommend_opening_windows_for_fresh_air")
        if profile.indoorContext.ventilationConstraints:
            modifiers.append("User noted ventilation constraints: passive window opening discouraged.")
        else:
            modifiers.append("Outdoor pollution too elevated for open-window ventilation.")
    else:
        allowed_themes.append("controlled_cross_ventilation")

    if profile.indoorContext.purifierAvailable:
        allowed_themes.append("hepa_purifier_operation")
        modifiers.append("Air purifier available: indoor filtration guidance prioritized.")
    else:
        prohibited_themes.append("assume_purifier_available")

    if profile.indoorContext.cookingExposure:
        allowed_themes.append("cooking_fume_exhaust_mitigation")
        modifiers.append("Cooking exposure present: kitchen exhaust and indoor particulate reduction included.")

    medical_disclaimer = is_vulnerable or effective_risk in {"high", "very_high", "severe"}
    if medical_disclaimer:
        flags.append("medical_disclaimer_required")

    if effective_risk == "severe":
        flags.append("safety_escalation_notice")

    return PolicyDecision(
        policyVersion=POLICY_VERSION,
        aqiStandard=telemetry.measurements.aqiStandard or AQI_STANDARD,
        riskCategory=effective_risk,
        freshnessStatus=freshness,
        flags=sorted(set(flags)),
        allowedThemes=allowed_themes,
        prohibitedThemes=prohibited_themes,
        profileModifiersApplied=modifiers or ["Standard adult baseline thresholds applied."],
        ventilationPermitted=ventilation_permitted,
        strenuousOutdoorDiscouraged=strenuous_discouraged,
        conservativeGuidanceRequired=conservative_required,
        medicalDisclaimerRequired=medical_disclaimer,
        aiGenerationAllowed=True,
    )
