"""Versioned prompt templates with optional externalized private prompts."""

import base64
import json
import os
from pathlib import Path

PROMPT_VERSION = "1.0.0"

_DEFAULT_SYSTEM_PROMPT_V1 = (
    "You are the grounded planning engine for Urban Air Quality Assistant. "
    "Convert VERIFIED_ENVIRONMENTAL_INPUTS and USER_PROFILE into valid JSON matching the schema. "
    "Never alter AQI, PM2.5, PM10, station, or timestamps; never diagnose or guarantee protection; "
    "respect policy_flags (especially ventilation_prohibited) and include profileDrivers."
)

_DEFAULT_REPAIR_PROMPT_TEMPLATE_V1 = (
    "Previous response failed validation: {validation_error}\n"
    "Return valid JSON matching the schema without altering verified metrics or violating policy_flags."
)

_DEFAULT_FOLLOWUP_SYSTEM_PROMPT_V1 = (
    "Answer only from VERIFIED_ENVIRONMENTAL_INPUTS, CURRENT_PLAN, and USER_PROFILE. "
    "Address the user's practical question directly, note if weather forecasts are unavailable, "
    "never invent readings or diagnoses, respect policy_flags, and return JSON {answer, nextStep}."
)


def _load_prompt_overrides() -> dict[str, str]:
    b64_raw = os.environ.get("PROMPTS_B64", "").strip()
    if b64_raw:
        try:
            decoded = base64.b64decode(b64_raw).decode("utf-8")
            parsed = json.loads(decoded)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items()}
        except Exception:
            pass

    local_file = Path(__file__).resolve().parent / "private_prompts.json"
    if local_file.is_file():
        try:
            parsed = json.loads(local_file.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items()}
        except Exception:
            pass
    return {}


_OVERRIDES = _load_prompt_overrides()

SYSTEM_PROMPT_V1 = _OVERRIDES.get("SYSTEM_PROMPT_V1", _DEFAULT_SYSTEM_PROMPT_V1)
REPAIR_PROMPT_TEMPLATE_V1 = _OVERRIDES.get("REPAIR_PROMPT_TEMPLATE_V1", _DEFAULT_REPAIR_PROMPT_TEMPLATE_V1)
FOLLOWUP_SYSTEM_PROMPT_V1 = _OVERRIDES.get("FOLLOWUP_SYSTEM_PROMPT_V1", _DEFAULT_FOLLOWUP_SYSTEM_PROMPT_V1)

USER_PROMPT_TEMPLATE_V1 = """VERIFIED_ENVIRONMENTAL_INPUTS:
- city: {city}
- station_name: {station_name}
- provider: {provider}
- provider_url: {provider_url}
- aqi: {aqi}
- pm25: {pm25}
- pm10: {pm10}
- unit: {unit}
- aqi_standard: {aqi_standard}
- observed_at: {observed_at}
- retrieved_at: {retrieved_at}
- freshness_status: {freshness_status}
- age_minutes: {age_minutes}
- deterministic_risk_category: {risk_category}
- policy_flags: {policy_flags}
- prohibited_themes: {prohibited_themes}

USER_PROFILE:
- household_members: {household_members}
- vulnerable_groups: {vulnerable_groups}
- commute_mode: {commute_mode}
- commute_time: {commute_time}
- planned_activities: {planned_activities}
- outdoor_worker_or_athlete: {outdoor_worker_or_athlete}
- indoor_purifier_available: {indoor_purifier_available}
- indoor_sensor_available: {indoor_sensor_available}
- cooking_exposure: {cooking_exposure}
- ventilation_constraints: {ventilation_constraints}
- priorities: {priorities}

TASK:
Create a morning-to-night plan for today (exactly 4 timeline periods: morning, afternoon, evening, night)."""

FOLLOWUP_USER_TEMPLATE_V1 = """VERIFIED_ENVIRONMENTAL_INPUTS:
- city: {city}
- station: {station_name}
- aqi: {aqi}
- pm25: {pm25}
- pm10: {pm10}
- observed_at: {observed_at}
- freshness: {freshness_status}
- risk_category: {risk_category}
- policy_flags: {policy_flags}

USER_PROFILE:
- household: {household_members}
- vulnerabilities: {vulnerable_groups}
- commute_mode: {commute_mode}
- purifier_available: {purifier_available}

CURRENT_PLAN_HEADLINE: {headline}
PRIORITY_ACTION: {priority_action}
TIMELINE_BY_PERIOD:
{timeline_summary}

USER_QUESTION:
{question}"""
