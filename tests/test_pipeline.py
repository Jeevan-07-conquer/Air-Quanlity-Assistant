"""Comprehensive unit, integration, prompt-eval, and security tests (SRD §13, Prompt 12)."""

import json
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.config.presets import SAMPLE_PRESETS
from app.lib.rate_limit import SlidingWindowRateLimiter
from app.schemas.analysis import AnalysisRequest, AnalysisOptions
from app.schemas.profile import UserProfile
from app.services.analysis_service import clear_analysis_cache, run_analysis
from app.services.environment_service import (
    clear_telemetry_cache,
    with_classified_freshness,
)
from app.services.followup_service import answer_followup_question
from app.services.llm_service import GroundedPlanInput, LLMProviderError, get_flash_candidate_models
from app.schemas.followup import FollowupRequest
from app.services.location_service import get_allowlisted_city, search_locations
from app.services.policy_service import evaluate_policy
from app.services.prompt_service import build_grounded_prompt
from app.services.providers.fixture_adapter import build_fixture_telemetry
from app.services.providers.waqi_adapter import ProviderError, normalize_waqi_payload
from app.services.telemetry_service import OBSERVABILITY
from app.services.validation_service import validate_ai_plan_output


def _preset_profile(preset_id: str) -> UserProfile:
    for p in SAMPLE_PRESETS:
        if p["id"] == preset_id:
            return UserProfile.model_validate(p["profile"])
    raise KeyError(preset_id)


class TestLocationAndPresets(unittest.TestCase):
    def test_supported_cities_and_unsupported_query(self) -> None:
        delhi = search_locations("delhi")
        self.assertEqual(delhi.resolutionStatus, "matched")
        self.assertEqual(delhi.matches[0].id, "delhi")

        unsupported = search_locations("Jaipur")
        self.assertEqual(unsupported.resolutionStatus, "unsupported")
        self.assertEqual(unsupported.matches, [])

        geo_match = search_locations(lat=19.08, lon=72.88)
        self.assertEqual(geo_match.resolutionStatus, "matched")
        self.assertEqual(geo_match.matches[0].id, "mumbai")

        geo_outside = search_locations(lat=51.50, lon=-0.12)
        self.assertEqual(geo_outside.resolutionStatus, "unsupported")

    def test_all_four_presets_validate_and_stay_marked_as_samples(self) -> None:
        self.assertGreaterEqual(len(SAMPLE_PRESETS), 4)
        for preset in SAMPLE_PRESETS:
            profile = UserProfile.model_validate(preset["profile"])
            self.assertTrue(profile.isSamplePreset)
            self.assertEqual(preset["badge"], "Sample profile")


class TestEnvironmentalAdapterAndFreshness(unittest.TestCase):
    def test_waqi_normalization_and_error_cases(self) -> None:
        city = get_allowlisted_city("delhi")
        assert city is not None
        now = datetime(2026, 11, 25, 4, 30, 0, tzinfo=timezone.utc)
        payload = {
            "status": "ok",
            "data": {
                "idx": 7024,
                "aqi": 285,
                "city": {"name": "Anand Vihar, Delhi", "url": "https://aqicn.org/city/delhi/anand-vihar/"},
                "iaqi": {"pm25": {"v": 152.4}, "pm10": {"v": 240.0}},
                "time": {"iso": "2026-11-25T04:10:00Z"},
            },
        }
        telemetry = with_classified_freshness(normalize_waqi_payload(city, payload, now=now))
        self.assertEqual(telemetry.measurements.aqi, 285.0)
        self.assertEqual(telemetry.measurements.pm25, 152.4)
        self.assertEqual(telemetry.freshness.status, "live")
        self.assertEqual(telemetry.freshness.ageMinutes, 20)

        with self.assertRaises(ProviderError) as quota_ctx:
            normalize_waqi_payload(city, {"status": "error", "data": "Over quota"})
        self.assertEqual(quota_ctx.exception.code, "provider_quota")

        with self.assertRaises(ProviderError) as empty_ctx:
            normalize_waqi_payload(city, {"status": "ok", "data": {"idx": 1, "city": {"name": "X"}, "iaqi": {}}})
        self.assertEqual(empty_ctx.exception.code, "no_station")

    def test_freshness_boundaries(self) -> None:
        city = get_allowlisted_city("mumbai")
        assert city is not None
        base = build_fixture_telemetry(city)

        for age, expected in [(30, "live"), (31, "recent"), (120, "recent"), (121, "stale"), (720, "stale"), (721, "unavailable")]:
            candidate = base.model_copy(
                update={"freshness": base.freshness.model_copy(update={"ageMinutes": age})}
            )
            classified = with_classified_freshness(candidate)
            self.assertEqual(classified.freshness.status, expected, f"age={age}")


class TestDeterministicPolicyEngine(unittest.TestCase):
    def test_table_driven_policy_thresholds_and_modifiers(self) -> None:
        city = get_allowlisted_city("mumbai")
        assert city is not None
        base = with_classified_freshness(build_fixture_telemetry(city))
        adult_profile = _preset_profile("delhi-working-professional")
        family_profile = _preset_profile("noida-family-toddler-senior")
        athlete_profile = _preset_profile("mumbai-outdoor-athlete")

        # Moderate reading (~80 AQI): standard adult allows ventilation; vulnerable family escalates to high & prohibits open windows
        mod_telemetry = base.model_copy(
            update={
                "measurements": base.measurements.model_copy(update={"aqi": 82.0, "pm25": 28.0, "pm10": 60.0})
            }
        )
        adult_policy = evaluate_policy(mod_telemetry, adult_profile)
        self.assertEqual(adult_policy.riskCategory, "moderate")
        self.assertTrue(adult_policy.ventilationPermitted)
        self.assertFalse(adult_policy.strenuousOutdoorDiscouraged)

        family_policy = evaluate_policy(mod_telemetry, family_profile)
        self.assertEqual(family_policy.riskCategory, "high")
        self.assertFalse(family_policy.ventilationPermitted)
        self.assertIn("ventilation_prohibited", family_policy.flags)

        athlete_policy = evaluate_policy(mod_telemetry, athlete_profile)
        self.assertTrue(athlete_policy.strenuousOutdoorDiscouraged)

        # Unavailable telemetry blocks AI generation
        unavail = with_classified_freshness(build_fixture_telemetry(city, simulate_mode="no_station"))
        unavail_policy = evaluate_policy(unavail, adult_profile)
        self.assertFalse(unavail_policy.aiGenerationAllowed)
        self.assertIn("ai_generation_blocked", unavail_policy.flags)


class TestPromptAndValidationSafety(unittest.TestCase):
    def test_prompt_preserves_exact_metrics_and_excludes_secrets(self) -> None:
        city = get_allowlisted_city("delhi")
        assert city is not None
        telemetry = with_classified_freshness(build_fixture_telemetry(city))
        profile = _preset_profile("delhi-working-professional")
        policy = evaluate_policy(telemetry, profile)

        prompt = build_grounded_prompt(telemetry, policy, profile, request_id="req-123")
        self.assertIn("aqi: 318", prompt.user_prompt)
        self.assertIn("pm25: 168.4", prompt.user_prompt)
        self.assertIn("pm10: 292", prompt.user_prompt)
        self.assertIn(telemetry.station.name, prompt.user_prompt)
        self.assertNotIn("WAQI_API_TOKEN", prompt.user_prompt)
        self.assertNotIn("GEMINI_API_KEY", prompt.user_prompt)

    def test_validator_rejects_tampered_metrics_medical_claims_and_prohibited_ventilation(self) -> None:
        city = get_allowlisted_city("delhi")
        assert city is not None
        telemetry = with_classified_freshness(build_fixture_telemetry(city))
        profile = _preset_profile("noida-family-toddler-senior")
        policy = evaluate_policy(telemetry, profile)

        # Generate a valid baseline plan first
        clear_telemetry_cache()
        clear_analysis_cache()
        with patch.dict(os.environ, {"TELEMETRY_MODE": "fixture", "WAQI_API_TOKEN": "", "GEMINI_API_KEY": ""}):
            good_resp = run_analysis(AnalysisRequest(locationId="delhi", profile=profile))
        good_dict = good_resp.plan.model_dump()

        # 1. Metric tampering
        tampered = json.loads(json.dumps(good_dict))
        tampered["headline"] = "Delhi AQI is 45 today so enjoy outdoor air."
        res_tamper = validate_ai_plan_output(tampered, telemetry, policy)
        self.assertFalse(res_tamper.valid)
        self.assertTrue(any("altered AQI" in e for e in res_tamper.errors))

        # 2. Medical diagnosis
        med = json.loads(json.dumps(good_dict))
        med["priority"]["action"] = "Take 20mg steroid dose and diagnose asthma before leaving."
        res_med = validate_ai_plan_output(med, telemetry, policy)
        self.assertFalse(res_med.valid)

        # 3. Prohibited ventilation violation
        vent = json.loads(json.dumps(good_dict))
        vent["indoorAirPlan"][0]["action"] = "Open all windows at 7 AM for fresh air."
        res_vent = validate_ai_plan_output(vent, telemetry, policy)
        self.assertFalse(res_vent.valid)

        # 4. XSS / HTML injection rejected
        xss = json.loads(json.dumps(good_dict))
        xss["headline"] = "<script>alert(1)</script>Delhi air is severe."
        res_xss = validate_ai_plan_output(xss, telemetry, policy)
        self.assertFalse(res_xss.valid)


class TestAnalysisPipelineAndFallbacks(unittest.TestCase):
    def setUp(self) -> None:
        self._env_patch = patch.dict(
            os.environ,
            {"TELEMETRY_MODE": "fixture", "WAQI_API_TOKEN": "", "GEMINI_API_KEY": ""},
        )
        self._env_patch.start()
        clear_telemetry_cache()
        clear_analysis_cache()

    def tearDown(self) -> None:
        self._env_patch.stop()

    def test_repair_retry_then_succeed_and_double_failure_fallback(self) -> None:
        profile = _preset_profile("delhi-working-professional")
        req = AnalysisRequest(locationId="delhi", profile=profile, options=AnalysisOptions(forceRefresh=True))
        baseline = run_analysis(req)
        valid_json = json.dumps(baseline.plan.model_dump())

        class RepairOnceProvider:
            def __init__(self) -> None:
                self.calls = 0

            def generate_plan_raw(self, plan_input: GroundedPlanInput) -> str:
                self.calls += 1
                if self.calls == 1:
                    return "{bad-json"
                if plan_input.repair_instruction is None:
                    raise AssertionError("Expected repair_instruction on second attempt")
                return valid_json

        repaired_provider = RepairOnceProvider()
        repaired_resp = run_analysis(req, provider_override=repaired_provider)
        self.assertEqual(repaired_provider.calls, 2)
        self.assertEqual(repaired_resp.status, "success")
        self.assertFalse(repaired_resp.degradedMode)

        class AlwaysBadProvider:
            def generate_plan_raw(self, _plan_input: GroundedPlanInput) -> str:
                return "{always-bad"

        fallback_resp = run_analysis(req, provider_override=AlwaysBadProvider())
        self.assertEqual(fallback_resp.status, "degraded")
        self.assertTrue(fallback_resp.degradedMode)
        self.assertEqual(fallback_resp.degradedReason, "ai_schema_validation_failed")
        self.assertEqual(len(fallback_resp.plan.timeline), 4)

    def test_failure_modes_and_profile_adaptation(self) -> None:
        prof = _preset_profile("delhi-working-professional")
        athlete = _preset_profile("mumbai-outdoor-athlete")

        # Profile adaptation: changing profile changes headline and drivers
        r1 = run_analysis(AnalysisRequest(locationId="mumbai", profile=prof))
        r2 = run_analysis(AnalysisRequest(locationId="mumbai", profile=athlete))
        self.assertNotEqual(r1.plan.headline, r2.plan.headline)

        # Simulated failure modes (Prompt 10)
        stale_resp = run_analysis(
            AnalysisRequest(locationId="delhi", profile=prof, options=AnalysisOptions(simulateMode="stale"))
        )
        self.assertEqual(stale_resp.telemetry.freshness.status, "stale")
        self.assertTrue(stale_resp.degradedMode)

        ai_timeout_resp = run_analysis(
            AnalysisRequest(locationId="delhi", profile=prof, options=AnalysisOptions(simulateMode="ai_timeout"))
        )
        self.assertEqual(ai_timeout_resp.status, "degraded")
        self.assertEqual(ai_timeout_resp.degradedReason, "ai_timeout")

        no_station_resp = run_analysis(
            AnalysisRequest(locationId="delhi", profile=prof, options=AnalysisOptions(simulateMode="no_station"))
        )
        self.assertEqual(no_station_resp.status, "unavailable")
        self.assertFalse(no_station_resp.policy.aiGenerationAllowed)

    def test_rate_limiter_and_redacted_observability(self) -> None:
        limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)
        self.assertTrue(limiter.allow("ip-1"))
        self.assertTrue(limiter.allow("ip-1"))
        self.assertFalse(limiter.allow("ip-1"))

        snap = OBSERVABILITY.snapshot()
        serialized = json.dumps(snap)
        self.assertNotIn("respiratory_condition", serialized)
        self.assertNotIn("WAQI_API_TOKEN", serialized)

    def test_followup_and_purifier_placement_and_model_fallback_order(self) -> None:
        models = get_flash_candidate_models("gemini-3.8-flash")
        self.assertEqual(models[0], "gemini-3.8-flash")
        self.assertIn("gemini-3.5-flash-lite", models)

        prof = _preset_profile("noida-family-toddler-senior")
        resp = run_analysis(AnalysisRequest(locationId="delhi", profile=prof))
        indoor_text = " ".join(f"{item.action} {item.caution}" for item in resp.plan.indoorAirPlan).lower()
        self.assertIn("purifier", indoor_text)
        self.assertIn("plant", indoor_text)

        f_resp = answer_followup_question(
            FollowupRequest(
                question="When should I open windows?",
                telemetry=resp.telemetry,
                policy=resp.policy,
                profile=prof,
                plan=resp.plan,
            )
        )
        self.assertTrue(len(f_resp.answer) > 10)
        self.assertTrue(len(f_resp.nextStep) > 5)


if __name__ == "__main__":
    unittest.main()
