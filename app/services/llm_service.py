"""Server-side Generative AI provider abstraction and shared Flash fallback helper (SRD §20)."""

from dataclasses import dataclass
import json
import os
from typing import Any, Optional, Protocol

from app.schemas.plan import GroundedPlan
from app.schemas.policy import PolicyDecision
from app.schemas.profile import UserProfile
from app.schemas.telemetry import EnvironmentalTelemetry
from app.services.fallback_service import build_deterministic_fallback_plan
from app.services.prompt_service import PromptPayload

DEFAULT_FLASH_MODEL = "gemini-3.5-flash-lite"
FALLBACK_FLASH_MODELS = ("gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash")


class LLMProviderError(Exception):
    """Structured AI provider failure (timeout, quota, refusal, or network error)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class GroundedPlanInput:
    """Typed input passed to a GenerativePlanProvider implementation."""

    telemetry: EnvironmentalTelemetry
    profile: UserProfile
    policy: PolicyDecision
    prompt: PromptPayload
    repair_instruction: Optional[str] = None


class GenerativePlanProvider(Protocol):
    """Protocol for structured JSON plan generators."""

    def generate_plan_raw(self, plan_input: GroundedPlanInput) -> str:
        """Return schema-constrained JSON string from the configured model."""
        ...


def get_flash_candidate_models(preferred_model: Optional[str] = None) -> list[str]:
    """Build a deduplicated Flash model order starting with the configured model."""
    primary = (preferred_model or os.environ.get("AI_MODEL", DEFAULT_FLASH_MODEL)).strip()
    candidates: list[str] = []
    for model in (primary, *FALLBACK_FLASH_MODELS):
        if model and model not in candidates:
            candidates.append(model)
    return candidates


def generate_gemini_json(
    *,
    api_key: str,
    system_instruction: str,
    user_content: str,
    response_schema: Any,
    max_output_tokens: int,
    timeout_ms: int = 20000,
    preferred_model: Optional[str] = None,
    thinking_budget: int = 512,
) -> str:
    """Call Google Gemini API with structured JSON output and automatic Flash fallback."""
    if not api_key:
        raise LLMProviderError("ai_unconfigured", "GEMINI_API_KEY is not configured on the server.")

    try:
        from google import genai
        from google.genai import errors as genai_errors
        from google.genai import types
    except ImportError as exc:
        raise LLMProviderError("ai_sdk_missing", "google-genai package is not available.") from exc

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=timeout_ms),
    )

    last_exc: Optional[Exception] = None
    for model in get_flash_candidate_models(preferred_model):
        cfg_kwargs: dict[str, Any] = {
            "system_instruction": system_instruction,
            "response_mime_type": "application/json",
            "response_schema": response_schema,
            "temperature": 0.2,
            "max_output_tokens": max_output_tokens,
        }
        if "lite" not in model.lower() and thinking_budget > 0:
            cfg_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)

        try:
            response = client.models.generate_content(
                model=model,
                contents=user_content,
                config=types.GenerateContentConfig(**cfg_kwargs),
            )
            text = getattr(response, "text", None)
            if not text or not text.strip():
                last_exc = LLMProviderError("ai_empty_or_refusal", "Model returned an empty response.")
                continue
            return text
        except TimeoutError as exc:
            last_exc = exc
            continue
        except genai_errors.APIError as exc:
            last_exc = exc
            msg = str(exc).lower()
            if "429" in msg or "quota" in msg or "resource_exhausted" in msg:
                raise LLMProviderError("ai_quota", "AI provider quota or rate limit exceeded.") from exc
            if any(code in msg for code in ("404", "503", "504", "unavailable", "not_found", "deadline", "timeout")):
                continue
            raise LLMProviderError("ai_unavailable", f"AI provider call failed: {type(exc).__name__}") from exc
        except (OSError, ValueError) as exc:
            last_exc = exc
            if "timeout" in str(exc).lower():
                continue
            raise LLMProviderError("ai_unavailable", f"AI transport failure: {type(exc).__name__}") from exc

    if isinstance(last_exc, LLMProviderError):
        raise last_exc
    if isinstance(last_exc, TimeoutError) or (
        last_exc is not None and any(tok in str(last_exc).lower() for tok in ("timeout", "deadline"))
    ):
        raise LLMProviderError("ai_timeout", "AI reasoning request timed out.") from last_exc
    raise LLMProviderError(
        "ai_unavailable",
        f"AI provider call failed: {type(last_exc).__name__ if last_exc else 'UnknownError'}",
    )


class GeminiPlanProvider:
    """Google Gemini API provider using google-genai structured JSON output."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None, timeout_ms: int = 20000):
        self.api_key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        self.model_name = (model_name or os.environ.get("AI_MODEL", DEFAULT_FLASH_MODEL)).strip()
        self.timeout_ms = timeout_ms

    def generate_plan_raw(self, plan_input: GroundedPlanInput) -> str:
        user_content = plan_input.prompt.user_prompt
        if plan_input.repair_instruction:
            user_content = f"{user_content}\n\n{plan_input.repair_instruction}"

        return generate_gemini_json(
            api_key=self.api_key,
            system_instruction=plan_input.prompt.system_prompt,
            user_content=user_content,
            response_schema=GroundedPlan,
            max_output_tokens=plan_input.prompt.token_budget,
            timeout_ms=self.timeout_ms,
            preferred_model=self.model_name,
            thinking_budget=512,
        )


class MockGroundedPlanProvider:
    """Deterministic profile-sensitive mock AI provider for local development & tests without live API keys."""

    def generate_plan_raw(self, plan_input: GroundedPlanInput) -> str:
        telemetry = plan_input.telemetry
        profile = plan_input.profile
        policy = plan_input.policy

        plan = build_deterministic_fallback_plan(
            telemetry,
            policy,
            profile,
            reason_note="Generated via local grounded mock AI engine (no live GEMINI_API_KEY configured).",
        )

        city = telemetry.location.city
        aqi_val = telemetry.measurements.aqi
        aqi_str = (
            f"AQI {int(aqi_val) if aqi_val and aqi_val.is_integer() else aqi_val}"
            if aqi_val is not None
            else "unavailable AQI"
        )

        custom_drivers = list(plan.profileDrivers)
        if profile.outdoorWorkerOrAthlete:
            plan.headline = (
                f"In {city} ({aqi_str}), shift high-exertion outdoor training indoors and monitor exertion windows."
            )
            plan.priority.title = "Pause intense outdoor training today"
            activity_name = (
                profile.plannedOutdoorActivity.activity
                if profile.plannedOutdoorActivity
                else "outdoor workout"
            )
            plan.priority.action = (
                f"Move your {activity_name} to an indoor space; elevated breathing rates multiply particulate intake."
            )
            custom_drivers.append("Athlete/outdoor worker exertion profile prioritized respiratory load reduction.")
        elif any(m in {"child", "senior", "pregnant"} for m in profile.household) or profile.vulnerabilities:
            plan.headline = (
                f"For your vulnerable household in {city} ({aqi_str}), prioritize clean indoor air and short enclosed trips."
            )
            plan.priority.title = "Protect children, seniors, and sensitive lungs indoors"
            custom_drivers.append("Vulnerable household safeguards tightened outdoor time and ventilation limits.")
        else:
            plan.headline = (
                f"For your {profile.commuteMode.replace('_', ' ')} routine in {city} ({aqi_str}), time travel away from peak pollution."
            )

        if profile.plannedOutdoorActivity:
            target_period = profile.plannedOutdoorActivity.preferredPeriod
            for entry in plan.timeline:
                if entry.period == target_period:
                    entry.recommendation = (
                        f"Planned activity ({profile.plannedOutdoorActivity.activity}): "
                        + (
                            "keep indoors or reschedule due to policy risk tier."
                            if policy.strenuousOutdoorDiscouraged
                            else "keep brief and away from heavy traffic."
                        )
                    )

        plan.profileDrivers = custom_drivers
        plan.confidence.level = "medium" if telemetry.freshness.status != "stale" else "low"
        plan.confidence.reason = (
            f"Grounded in verified {telemetry.station.name} telemetry ({telemetry.freshness.status}) "
            f"and policy v{policy.policyVersion}."
        )
        return json.dumps(plan.model_dump(), ensure_ascii=False)


class _SimulatedFailureProvider:
    def __init__(self, mode: str):
        self.mode = mode

    def generate_plan_raw(self, _plan_input: GroundedPlanInput) -> str:
        if self.mode == "ai_timeout":
            raise LLMProviderError("ai_timeout", "Simulated AI model timeout.")
        if self.mode == "ai_unavailable":
            raise LLMProviderError("ai_unavailable", "Simulated AI service unavailability.")
        if self.mode == "ai_invalid_json":
            return "{not-valid-json"
        raise LLMProviderError("ai_unavailable", "Unknown simulated mode.")


def resolve_plan_provider(simulate_mode: Optional[str] = None) -> GenerativePlanProvider:
    """Select server-configured Gemini provider or fallback mock provider."""
    if simulate_mode in {"ai_timeout", "ai_invalid_json", "ai_unavailable"}:
        return _SimulatedFailureProvider(simulate_mode)

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    ai_provider = os.environ.get("AI_PROVIDER", "google").strip().lower()
    if ai_provider == "google" and api_key:
        timeout_ms = int(os.environ.get("AI_TIMEOUT_MS", "20000"))
        model_name = os.environ.get("AI_MODEL", DEFAULT_FLASH_MODEL)
        return GeminiPlanProvider(api_key=api_key, model_name=model_name, timeout_ms=timeout_ms)
    return MockGroundedPlanProvider()
