"""Deterministic fallback plan builder when AI is unavailable, fails validation, or telemetry is missing (SRD FR-10, §8.6)."""

from app.config.policy_thresholds import ANALYSIS_VERSION, PERSISTENT_SAFETY_NOTICE
from app.schemas.plan import (
    ConfidenceInfo,
    GroundedPlan,
    IndoorAirItem,
    MobilityOption,
    PrioritySummary,
    TimelineAction,
    TimelinePeriod,
)
from app.schemas.policy import PolicyDecision
from app.schemas.profile import UserProfile
from app.schemas.telemetry import EnvironmentalTelemetry


def _metric_summary(telemetry: EnvironmentalTelemetry) -> str:
    m = telemetry.measurements
    parts: list[str] = []
    if m.aqi is not None:
        parts.append(f"AQI {int(m.aqi) if m.aqi.is_integer() else m.aqi}")
    if m.pm25 is not None:
        parts.append(f"PM2.5 {m.pm25} {m.unit}")
    if m.pm10 is not None:
        parts.append(f"PM10 {m.pm10} {m.unit}")
    return ", ".join(parts) if parts else "no numeric particulate readings available"


def build_deterministic_fallback_plan(
    telemetry: EnvironmentalTelemetry,
    policy: PolicyDecision,
    profile: UserProfile,
    reason_note: str = "AI reasoning unavailable; showing deterministic policy-based safety plan.",
) -> GroundedPlan:
    """Produce a safe, schema-valid, profile-aware deterministic plan without an LLM."""
    city = telemetry.location.city
    metrics_text = _metric_summary(telemetry)
    risk = policy.riskCategory
    vulnerable = any(m in {"child", "senior", "pregnant"} for m in profile.household) or bool(
        profile.vulnerabilities
    )

    if policy.freshnessStatus == "unavailable":
        headline = f"Verified air-quality readings for {city} are currently unavailable; apply conservative precautions."
        priority = PrioritySummary(
            level="unknown",
            title="Retry telemetry check before planning strenuous outdoor activity",
            action="Hold non-essential strenuous outdoor exertion until a verified station reading is restored.",
            reason="No trustworthy live or recent monitoring station data is available right now.",
        )
    elif risk in {"very_high", "severe"}:
        headline = f"{city} is at {risk.replace('_', ' ')} risk ({metrics_text}); shift activities indoors and minimize exposure."
        priority = PrioritySummary(
            level=risk,
            title="Move planned outdoor exertion indoors and keep windows closed",
            action="Replace outdoor workouts or long walks with indoor alternatives and run filtration if available.",
            reason=f"Verified station reading ({metrics_text}) places {city} in the {risk.replace('_', ' ')} policy tier.",
        )
    elif risk == "high":
        headline = f"{city} shows elevated pollution ({metrics_text}); shorten outdoor exposure and prioritize lower-exertion windows."
        priority = PrioritySummary(
            level="high",
            title="Avoid strenuous outdoor exertion and favor enclosed transit",
            action="Keep outdoor trips brief, avoid peak traffic corridors, and protect vulnerable household members.",
            reason=f"Verified reading ({metrics_text}) combined with your profile requires elevated caution.",
        )
    else:
        headline = f"{city} currently measures {metrics_text} ({risk} tier); plan outdoor errands thoughtfully around traffic hours."
        priority = PrioritySummary(
            level=risk,
            title="Schedule outdoor tasks away from peak roadside traffic",
            action="Complete priority outdoor routines during calmer mid-day or low-traffic windows.",
            reason=f"Verified reading ({metrics_text}) remains manageable for general routines with standard care.",
        )

    ventilation_action = (
        "Open windows briefly for cross-ventilation only during lower-traffic hours."
        if policy.ventilationPermitted
        else "Keep exterior windows and balcony doors closed; do not open windows for fresh air while outdoor risk is elevated."
    )

    purifier_note = (
        "Place your HEPA air purifier centrally in the closed bedroom or main living room away from doors/walls and run continuously."
        if profile.indoorContext.purifierAvailable
        else "Keep doors closed in main living/sleeping areas and wet-mop dust instead of dry sweeping."
    )

    period_specs = [
        ("morning", "06:00-10:00", "Keep morning commute or school travel brief and avoid high-intensity outdoor exercise."),
        ("afternoon", "12:00-16:00", "If an essential errand is needed, mid-afternoon typically has better dispersion than rush hours."),
        ("evening", "17:00-21:00", "Avoid roadside walking/cycling during evening peak congestion when particulates accumulate."),
        ("night", "21:00-06:00", "Focus on clean sleeping-room air and keep windows sealed if outdoor pollution remains high."),
    ]

    timeline: list[TimelinePeriod] = []
    for period, window, rec in period_specs:
        period_risk = risk if period in {"morning", "evening", "night"} else ("moderate" if risk == "high" else risk)
        timeline.append(
            TimelinePeriod(
                period=period,  # type: ignore[arg-type]
                window=window,
                risk=period_risk,
                recommendation=rec,
                actions=[
                    TimelineAction(
                        title=f"{period.capitalize()} exposure precaution",
                        condition=f"{city} deterministic policy tier is {risk} ({metrics_text}).",
                        action=rec,
                        reason="Reduces inhaled particulate load during routine daily transitions.",
                        benefit="Lowers cumulative exposure across commuting and household schedules.",
                        tradeoff="Requires adjusting timing or shifting vigorous activity indoors.",
                        priority="must_do" if risk in {"high", "very_high", "severe"} else "recommended",
                    )
                ],
                indoorAlternative=purifier_note,
            )
        )

    indoor_items = [
        IndoorAirItem(
            title="Ventilation & containment",
            action=ventilation_action,
            reason="Outdoor particulate levels and household constraints govern safe window opening.",
            when="Throughout today until conditions improve",
            caution="Indoor plants add comfort but cannot replace mechanical HEPA filtration during severe smog.",
        ),
        IndoorAirItem(
            title="Purifier placement & indoor particulate control",
            action=purifier_note,
            reason="Limits indoor buildup from outdoor infiltration and household dust.",
            when="Especially during morning and night hours",
            caution="Use kitchen exhaust or lid cooking when preparing meals."
            if profile.indoorContext.cookingExposure
            else "Avoid burning incense, candles, or indoor smoke.",
        ),
    ]

    mobility_options = [
        MobilityOption(
            option="Enclosed public transit (metro) or carpool with recirculated cabin air",
            bestFor=f"Your {profile.commuteMode.replace('_', ' ')} commute",
            whyItHelps="Reduces direct roadside inhalation compared with open two-wheeler or brisk walking.",
            tradeoff="May add minor transit transfer time compared with door-to-door travel.",
        ),
        MobilityOption(
            option="Combine errands into a single off-peak trip",
            bestFor="Household errands and school runs",
            whyItHelps="Cuts total outdoor minutes and lowers personal and local tailpipe emissions.",
            tradeoff="Requires grouping stops rather than multiple short trips.",
        ),
    ]

    drivers = list(policy.profileModifiersApplied)
    drivers.append(f"Commute mode set to {profile.commuteMode.replace('_', ' ')}.")
    if profile.plannedOutdoorActivity:
        drivers.append(
            f"Planned activity noted: {profile.plannedOutdoorActivity.activity} ({profile.plannedOutdoorActivity.preferredPeriod})."
        )
    if vulnerable:
        drivers.append("Vulnerable household safeguards applied.")

    limitations = [
        reason_note,
        f"Station data reflects {telemetry.station.name} ({telemetry.freshness.status} status).",
    ]
    if telemetry.measurements.pm10 is None or telemetry.measurements.pm25 is None:
        limitations.append("Partial pollutant readings: one particulate metric was unavailable from the provider.")
    if not profile.indoorContext.indoorSensorAvailable:
        limitations.append("No indoor air sensor is connected; indoor air quality is not directly measured.")

    confidence_level = "low" if telemetry.freshness.status in {"stale", "unavailable"} else "medium"
    return GroundedPlan(
        analysisVersion=ANALYSIS_VERSION,
        headline=headline,
        priority=priority,
        timeline=timeline,
        indoorAirPlan=indoor_items,
        mobilityOptions=mobility_options,
        profileDrivers=drivers,
        limitations=limitations,
        safetyNote=PERSISTENT_SAFETY_NOTICE,
        confidence=ConfidenceInfo(
            level=confidence_level,  # type: ignore[arg-type]
            reason="Generated by deterministic safety rules without live LLM personalization.",
        ),
    )
