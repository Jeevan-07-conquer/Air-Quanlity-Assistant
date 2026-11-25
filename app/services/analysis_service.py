"""End-to-end analysis orchestrator implementing the 10-step lifecycle (SRD §9.4, Prompt 08)."""

import hashlib
import json
import time
from typing import Optional
import uuid

from app.config.policy_thresholds import ANALYSIS_CACHE_TTL_SECONDS, ANALYSIS_VERSION
from app.prompts.templates import PROMPT_VERSION
from app.schemas.analysis import AnalysisRequest, AnalysisResponse, ProvenanceInfo
from app.services.environment_service import get_latest_reading
from app.services.fallback_service import build_deterministic_fallback_plan
from app.services.llm_service import (
    GenerativePlanProvider,
    GroundedPlanInput,
    LLMProviderError,
    resolve_plan_provider,
)
from app.services.location_service import get_allowlisted_city
from app.services.policy_service import evaluate_policy
from app.services.prompt_service import build_grounded_prompt, build_repair_prompt
from app.services.telemetry_service import OBSERVABILITY
from app.services.validation_service import validate_ai_plan_output

_ANALYSIS_CACHE: dict[str, tuple[float, AnalysisResponse]] = {}
MAX_ANALYSIS_CACHE_ENTRIES = 500


def clear_analysis_cache() -> None:
    _ANALYSIS_CACHE.clear()


def _store_analysis_cache(cache_key: str, response: AnalysisResponse) -> None:
    now_mono = time.monotonic()
    if len(_ANALYSIS_CACHE) >= MAX_ANALYSIS_CACHE_ENTRIES:
        expired = [k for k, (exp, _) in _ANALYSIS_CACHE.items() if exp <= now_mono]
        for k in expired:
            del _ANALYSIS_CACHE[k]
        while len(_ANALYSIS_CACHE) >= MAX_ANALYSIS_CACHE_ENTRIES:
            del _ANALYSIS_CACHE[next(iter(_ANALYSIS_CACHE))]
    _ANALYSIS_CACHE[cache_key] = (now_mono + ANALYSIS_CACHE_TTL_SECONDS, response)


def _analysis_cache_key(request: AnalysisRequest, observed_at: str, policy_version: str) -> str:
    payload = json.dumps(
        {
            "locationId": request.locationId,
            "observedAt": observed_at,
            "policyVersion": policy_version,
            "promptVersion": PROMPT_VERSION,
            "profile": request.profile.model_dump(),
            "simulateMode": request.options.simulateMode,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_analysis(
    request: AnalysisRequest,
    provider_override: Optional[GenerativePlanProvider] = None,
) -> AnalysisResponse:
    """Execute the grounded environmental -> policy -> prompt -> LLM -> validation -> fallback pipeline."""
    request_id = str(uuid.uuid4())
    city = get_allowlisted_city(request.locationId)
    if city is None:
        raise ValueError(f"Unsupported locationId: {request.locationId}")

    sim_mode = request.options.simulateMode

    t_prov_start = time.monotonic()
    telemetry, provider_issue = get_latest_reading(
        city,
        simulate_mode=sim_mode,
        force_refresh=request.options.forceRefresh,
    )
    provider_latency_ms = int((time.monotonic() - t_prov_start) * 1000)

    policy = evaluate_policy(telemetry, request.profile)

    cache_key = _analysis_cache_key(request, telemetry.source.observedAt, policy.policyVersion)
    if not request.options.forceRefresh and sim_mode in (None, "normal") and cache_key in _ANALYSIS_CACHE:
        expires_at, cached_resp = _ANALYSIS_CACHE[cache_key]
        if time.monotonic() < expires_at:
            return cached_resp.model_copy(update={"requestId": request_id})

    provenance = ProvenanceInfo(
        provider=telemetry.source.provider,
        sourceUrl=telemetry.source.url,
        observedAt=telemetry.source.observedAt,
        retrievedAt=telemetry.source.retrievedAt,
        analysisVersion=ANALYSIS_VERSION,
        policyVersion=policy.policyVersion,
        promptVersion=PROMPT_VERSION,
    )

    # Hard boundary: when telemetry is unavailable, AI generation is blocked (FR-05)
    if not policy.aiGenerationAllowed:
        reason = (
            "Provider timeout prevented a fresh reading."
            if provider_issue == "provider_timeout"
            else "Provider quota exceeded."
            if provider_issue == "provider_quota"
            else "No active monitoring station reading available."
        )
        fallback_plan = build_deterministic_fallback_plan(telemetry, policy, request.profile, reason_note=reason)
        response = AnalysisResponse(
            requestId=request_id,
            status="unavailable",
            telemetry=telemetry,
            policy=policy,
            plan=fallback_plan,
            provenance=provenance,
            limitations=fallback_plan.limitations,
            degradedMode=True,
            degradedReason=provider_issue or "telemetry_unavailable",
        )
        OBSERVABILITY.record(
            request_id=request_id,
            location_id=city.id,
            status=response.status,
            freshness=telemetry.freshness.status,
            provider_latency_ms=provider_latency_ms,
            llm_latency_ms=0,
            provider_failed=provider_issue is not None,
            validation_failed=False,
            repair_attempted=False,
        )
        return response

    prompt_payload = build_grounded_prompt(
        telemetry=telemetry,
        policy=policy,
        profile=request.profile,
        request_id=request_id,
    )
    llm_provider = provider_override or resolve_plan_provider(sim_mode)

    t_llm_start = time.monotonic()
    validation_failed = False
    repair_attempted = False
    degraded_mode = provider_issue is not None or telemetry.freshness.status == "stale"
    degraded_reason: Optional[str] = provider_issue or ("stale_telemetry" if telemetry.freshness.status == "stale" else None)

    validated_plan = None
    try:
        raw_json = llm_provider.generate_plan_raw(
            GroundedPlanInput(
                telemetry=telemetry,
                profile=request.profile,
                policy=policy,
                prompt=prompt_payload,
            )
        )
        val_result = validate_ai_plan_output(raw_json, telemetry, policy)
        if not val_result.valid:
            validation_failed = True
            repair_attempted = True
            repair_text = build_repair_prompt("; ".join(val_result.errors))
            raw_repair = llm_provider.generate_plan_raw(
                GroundedPlanInput(
                    telemetry=telemetry,
                    profile=request.profile,
                    policy=policy,
                    prompt=prompt_payload,
                    repair_instruction=repair_text,
                )
            )
            repair_result = validate_ai_plan_output(raw_repair, telemetry, policy)
            if repair_result.valid and repair_result.plan is not None:
                validated_plan = repair_result.plan
            else:
                degraded_mode = True
                degraded_reason = "ai_schema_validation_failed"
                validated_plan = build_deterministic_fallback_plan(
                    telemetry,
                    policy,
                    request.profile,
                    reason_note="AI response failed validation twice; switched to deterministic safety fallback.",
                )
        else:
            validated_plan = val_result.plan
    except LLMProviderError as err:
        degraded_mode = True
        degraded_reason = err.code
        validated_plan = build_deterministic_fallback_plan(
            telemetry,
            policy,
            request.profile,
            reason_note=f"AI reasoning unavailable ({err.message}); showing deterministic safety plan.",
        )

    llm_latency_ms = int((time.monotonic() - t_llm_start) * 1000)
    assert validated_plan is not None

    limitations = list(validated_plan.limitations)
    if provider_issue == "provider_timeout":
        limitations.insert(0, "Live provider timed out; displaying last verified reading with stale caution.")

    status = "degraded" if degraded_mode else "success"
    response = AnalysisResponse(
        requestId=request_id,
        status=status,
        telemetry=telemetry,
        policy=policy,
        plan=validated_plan,
        provenance=provenance,
        limitations=limitations,
        degradedMode=degraded_mode,
        degradedReason=degraded_reason,
    )

    if not degraded_mode and sim_mode in (None, "normal"):
        _store_analysis_cache(cache_key, response)

    OBSERVABILITY.record(
        request_id=request_id,
        location_id=city.id,
        status=status,
        freshness=telemetry.freshness.status,
        provider_latency_ms=provider_latency_ms,
        llm_latency_ms=llm_latency_ms,
        provider_failed=provider_issue is not None,
        validation_failed=validation_failed,
        repair_attempted=repair_attempted,
    )
    return response
