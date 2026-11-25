"""Post-generation AI output schema, metric consistency, and safety validator (SRD §8.6, Prompt 07)."""

from dataclasses import dataclass
import json
import re
from typing import Any, Optional

from pydantic import ValidationError

from app.schemas.plan import GroundedPlan
from app.schemas.policy import PolicyDecision
from app.schemas.telemetry import EnvironmentalTelemetry

MEDICAL_DIAGNOSIS_PATTERNS = [
    re.compile(r"\b(?<!not\s)(?<!no\s)(diagnos(e|ed|ing)|you\s+have\s+(asthma|copd|bronchitis)|prescrib(e|ed|ing)|take\s+\d+\s*mg|inhaler\s+dosage|antibiotic|steroid\s+dose)\b", re.I),
    re.compile(r"\b(?<!not\s)(?<!no\s)(?<!not\sa\s)medical\s+diagnosis\b", re.I),
]

GUARANTEE_PATTERNS = [
    re.compile(r"\b(100%\s*(safe|protected|protection|clean)|guarantees?\s+(protection|safe|zero\s+exposure)|makes\s+hazardous\s+air\s+harmless)\b", re.I),
]

HTML_MARKDOWN_PATTERNS = [
    re.compile(r"<\s*(script|iframe|img|div|span|p|a|b|strong)\b", re.I),
    re.compile(r"```"),
]

OPEN_WINDOW_PATTERN = re.compile(
    r"\b(?<!do\snot\s)(?<!don't\s)(?<!never\s)(?<!avoid\s)(open\s+(all\s+)?windows|keep\s+windows\s+open|ventilate\s+by\s+opening\s+windows)\b",
    re.I,
)

METRIC_MENTION_PATTERNS = {
    "aqi": re.compile(r"\bAQI\s*(?:is|of|:|=)?\s*(\d+(?:\.\d+)?)\b", re.I),
    "pm25": re.compile(r"\bPM\s*2\.?5\s*(?:is|of|:|=)?\s*(\d+(?:\.\d+)?)\b", re.I),
    "pm10": re.compile(r"\bPM\s*10\s*(?:is|of|:|=)?\s*(\d+(?:\.\d+)?)\b", re.I),
}


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    plan: Optional[GroundedPlan]
    errors: list[str]


def _collect_all_text(plan: GroundedPlan) -> str:
    parts: list[str] = [
        plan.headline,
        plan.priority.title,
        plan.priority.action,
        plan.priority.reason,
        plan.safetyNote,
        plan.confidence.reason,
        *plan.profileDrivers,
        *plan.limitations,
    ]
    for item in plan.timeline:
        parts.extend([item.recommendation, item.indoorAlternative])
        for act in item.actions:
            parts.extend([act.title, act.condition, act.action, act.reason, act.benefit, act.tradeoff])
    for indoor in plan.indoorAirPlan:
        parts.extend([indoor.title, indoor.action, indoor.reason, indoor.when, indoor.caution])
    for mob in plan.mobilityOptions:
        parts.extend([mob.option, mob.bestFor, mob.whyItHelps, mob.tradeoff])
    return "\n".join(parts)


def _check_metric_consistency(text: str, telemetry: EnvironmentalTelemetry) -> list[str]:
    errors: list[str] = []
    actuals = {
        "aqi": telemetry.measurements.aqi,
        "pm25": telemetry.measurements.pm25,
        "pm10": telemetry.measurements.pm10,
    }

    for key, pattern in METRIC_MENTION_PATTERNS.items():
        actual = actuals[key]
        for match in pattern.finditer(text):
            mentioned = float(match.group(1))
            if actual is None:
                errors.append(f"AI invented {key.upper()}={mentioned} when verified reading is unavailable.")
            elif abs(mentioned - actual) > 0.5:
                errors.append(
                    f"AI altered {key.upper()} ({mentioned}) away from verified telemetry ({actual})."
                )
    return errors


def validate_ai_plan_output(
    raw_output: str | dict[str, Any],
    telemetry: EnvironmentalTelemetry,
    policy: PolicyDecision,
) -> ValidationResult:
    """Validate untrusted LLM JSON against Plan schema and deterministic safety rules."""
    errors: list[str] = []

    if isinstance(raw_output, str):
        stripped = raw_output.strip()
        if not stripped:
            return ValidationResult(valid=False, plan=None, errors=["Empty AI response."])
        try:
            parsed: Any = json.loads(stripped)
        except json.JSONDecodeError as exc:
            return ValidationResult(valid=False, plan=None, errors=[f"Invalid JSON: {exc.msg}"])
    elif isinstance(raw_output, dict):
        parsed = raw_output
    else:
        return ValidationResult(valid=False, plan=None, errors=["Unsupported AI output payload type."])

    try:
        plan = GroundedPlan.model_validate(parsed)
    except ValidationError as exc:
        err_msgs = [f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()[:5]]
        return ValidationResult(valid=False, plan=None, errors=err_msgs)

    periods = {t.period for t in plan.timeline}
    if periods != {"morning", "afternoon", "evening", "night"}:
        errors.append("Timeline must include morning, afternoon, evening, and night periods.")

    full_text = _collect_all_text(plan)
    if len(full_text) > 9500:
        errors.append("Generated plan exceeds UI length budget.")

    for pat in HTML_MARKDOWN_PATTERNS:
        if pat.search(full_text):
            errors.append("Unsupported HTML or markdown code fences detected in AI output.")
            break

    for pat in MEDICAL_DIAGNOSIS_PATTERNS:
        if pat.search(full_text):
            errors.append("Medical diagnosis or medication instruction detected.")
            break

    for pat in GUARANTEE_PATTERNS:
        if pat.search(full_text):
            errors.append("Unsupported guarantee or overclaiming detected.")
            break

    if not policy.ventilationPermitted and OPEN_WINDOW_PATTERN.search(full_text):
        errors.append("Recommended opening windows while ventilation_prohibited policy flag is active.")

    if not any(d.strip() for d in plan.profileDrivers):
        errors.append("Missing profileDrivers explaining how the user profile shaped the plan.")

    errors.extend(_check_metric_consistency(full_text, telemetry))

    if errors:
        return ValidationResult(valid=False, plan=None, errors=errors)
    return ValidationResult(valid=True, plan=plan, errors=[])
