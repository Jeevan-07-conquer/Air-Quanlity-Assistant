"""Grounded conversational follow-up service using shared Gemini helper & safety checks (SRD §8.8)."""

import json
import os
from typing import Optional

from pydantic import ValidationError

from app.prompts.templates import FOLLOWUP_SYSTEM_PROMPT_V1, FOLLOWUP_USER_TEMPLATE_V1
from app.schemas.followup import FollowupRequest, FollowupResponse
from app.services.llm_service import LLMProviderError, generate_gemini_json
from app.services.validation_service import check_safety_text


def _fmt_num(val: Optional[float]) -> str:
    if val is None:
        return "unavailable"
    return str(int(val)) if val.is_integer() else str(val)


def _deterministic_followup(req: FollowupRequest) -> FollowupResponse:
    city = req.telemetry.location.city
    aqi_txt = _fmt_num(req.telemetry.measurements.aqi)
    q = req.question.lower()

    if "window" in q or "ventilat" in q:
        if req.policy.ventilationPermitted:
            ans = (
                f"In {city} (AQI {aqi_txt}), brief cross-ventilation is permitted during lower-traffic hours, "
                "though you should close windows if traffic smoke or cooking fumes build up outside."
            )
            step = "Open windows briefly during midday off-peak hours, then close them before evening rush hour."
        else:
            ans = (
                f"In {city} (AQI {aqi_txt}), opening windows is not recommended right now because outdoor air risk "
                f"is {req.policy.riskCategory.replace('_', ' ')}."
            )
            step = (
                "Keep windows closed and run your air purifier centrally in the occupied room."
                if req.profile.indoorContext.purifierAvailable
                else "Keep exterior windows shut and reduce indoor smoke from cooking or incense."
            )
        return FollowupResponse(answer=ans, nextStep=step, degradedMode=True)

    return FollowupResponse(
        answer=(
            f"Based on {city}'s current reading (AQI {aqi_txt}, {req.telemetry.freshness.status} status) "
            f"and your {req.profile.commuteMode.replace('_', ' ')} routine, {req.plan.priority.action}"
        ),
        nextStep=req.plan.priority.title,
        degradedMode=True,
    )


def _validate_followup(raw_text: str, req: FollowupRequest) -> Optional[FollowupResponse]:
    try:
        resp = FollowupResponse.model_validate(json.loads(raw_text))
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        return None

    combined = f"{resp.answer}\n{resp.nextStep}"
    if len(resp.answer.split()) > 135:
        return None
    if check_safety_text(combined, req.telemetry, req.policy):
        return None
    return resp


def answer_followup_question(req: FollowupRequest) -> FollowupResponse:
    """Answer a user follow-up question strictly grounded in verified telemetry and current plan."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    ai_provider = os.environ.get("AI_PROVIDER", "google").strip().lower()
    if ai_provider != "google" or not api_key:
        return _deterministic_followup(req)

    timeline_lines = [
        f"- {slot.period} ({slot.window}, {slot.risk} risk): {slot.recommendation}"
        for slot in req.plan.timeline
    ]

    user_content = FOLLOWUP_USER_TEMPLATE_V1.format(
        city=req.telemetry.location.city,
        station_name=req.telemetry.station.name,
        aqi=_fmt_num(req.telemetry.measurements.aqi),
        pm25=_fmt_num(req.telemetry.measurements.pm25),
        pm10=_fmt_num(req.telemetry.measurements.pm10),
        observed_at=req.telemetry.source.observedAt,
        freshness_status=req.telemetry.freshness.status,
        risk_category=req.policy.riskCategory,
        policy_flags=", ".join(req.policy.flags) if req.policy.flags else "none",
        household_members=", ".join(req.profile.household),
        vulnerable_groups=", ".join(req.profile.vulnerabilities) if req.profile.vulnerabilities else "none",
        commute_mode=req.profile.commuteMode,
        purifier_available=str(req.profile.indoorContext.purifierAvailable).lower(),
        headline=req.plan.headline,
        priority_action=req.plan.priority.action,
        timeline_summary="\n".join(timeline_lines),
        question=req.question.strip(),
    )

    timeout_ms = int(os.environ.get("AI_TIMEOUT_MS", "20000"))
    try:
        raw_text = generate_gemini_json(
            api_key=api_key,
            system_instruction=FOLLOWUP_SYSTEM_PROMPT_V1,
            user_content=user_content,
            response_schema=FollowupResponse,
            max_output_tokens=600,
            timeout_ms=timeout_ms,
            thinking_budget=256,
        )
    except LLMProviderError:
        return _deterministic_followup(req)

    validated = _validate_followup(raw_text, req)
    if validated is not None:
        return validated.model_copy(update={"degradedMode": False})
    return _deterministic_followup(req)
