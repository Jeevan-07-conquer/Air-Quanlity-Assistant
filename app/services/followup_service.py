"""Grounded conversational follow-up service using Gemini Flash with safety checks (SRD §8.8)."""

import json
import os
from typing import Optional

from app.prompts.templates import FOLLOWUP_SYSTEM_PROMPT_V1, FOLLOWUP_USER_TEMPLATE_V1
from app.schemas.followup import FollowupRequest, FollowupResponse
from app.services.llm_service import DEFAULT_FLASH_MODEL, FALLBACK_FLASH_MODELS
from app.services.validation_service import (
    GUARANTEE_PATTERNS,
    HTML_MARKDOWN_PATTERNS,
    MEDICAL_DIAGNOSIS_PATTERNS,
    OPEN_WINDOW_PATTERN,
    _check_metric_consistency,
)


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
                "Keep windows closed and run your air purifier in the main living room."
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
        data = json.loads(raw_text)
        resp = FollowupResponse.model_validate(data)
    except Exception:
        return None

    combined = f"{resp.answer}\n{resp.nextStep}"
    if len(resp.answer.split()) > 135:
        return None
    for pat in (*HTML_MARKDOWN_PATTERNS, *MEDICAL_DIAGNOSIS_PATTERNS, *GUARANTEE_PATTERNS):
        if pat.search(combined):
            return None
    if not req.policy.ventilationPermitted and OPEN_WINDOW_PATTERN.search(combined):
        return None
    if _check_metric_consistency(combined, req.telemetry):
        return None
    return resp


def answer_followup_question(req: FollowupRequest) -> FollowupResponse:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    ai_provider = os.environ.get("AI_PROVIDER", "google").strip().lower()
    if ai_provider != "google" or not api_key:
        return _deterministic_followup(req)

    try:
        from google import genai
        from google.genai import types
    except ImportError:
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

    configured = os.environ.get("AI_MODEL", DEFAULT_FLASH_MODEL).strip()
    candidates: list[str] = []
    for m in (configured, *FALLBACK_FLASH_MODELS):
        if m and m not in candidates:
            candidates.append(m)

    timeout_ms = int(os.environ.get("AI_TIMEOUT_MS", "20000"))
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_ms))

    for model in candidates:
        cfg_kwargs: dict = {
            "system_instruction": FOLLOWUP_SYSTEM_PROMPT_V1,
            "response_mime_type": "application/json",
            "response_schema": FollowupResponse,
            "temperature": 0.2,
            "max_output_tokens": 600,
        }
        if "lite" not in model.lower():
            cfg_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=256)

        try:
            res = client.models.generate_content(
                model=model,
                contents=user_content,
                config=types.GenerateContentConfig(**cfg_kwargs),
            )
            text = getattr(res, "text", None)
            if not text:
                continue
            validated = _validate_followup(text, req)
            if validated is not None:
                return validated.model_copy(update={"degradedMode": False})
        except Exception:
            continue

    return _deterministic_followup(req)
