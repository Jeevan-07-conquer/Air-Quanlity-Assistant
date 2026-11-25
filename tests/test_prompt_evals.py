"""Prompt evaluation fixture matrix covering SRD §13.4 scenarios."""

import os
import unittest
from unittest.mock import patch

from app.schemas.analysis import AnalysisRequest
from app.schemas.profile import IndoorContext, PlannedOutdoorActivity, UserProfile
from app.services.analysis_service import clear_analysis_cache, run_analysis
from app.services.environment_service import clear_telemetry_cache, with_classified_freshness
from app.services.location_service import get_allowlisted_city
from app.services.policy_service import evaluate_policy
from app.services.providers.fixture_adapter import build_fixture_telemetry
from app.services.validation_service import validate_ai_plan_output
from app.services.llm_service import GroundedPlanInput, MockGroundedPlanProvider
from app.services.prompt_service import build_grounded_prompt


class TestPromptEvaluationMatrix(unittest.TestCase):
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

    def test_low_moderate_high_severe_and_conflicting_inputs(self) -> None:
        city = get_allowlisted_city("delhi")
        assert city is not None
        base_telemetry = build_fixture_telemetry(city)

        conflicting_athlete = UserProfile(
            household=["adult"],
            vulnerabilities=[],
            primaryActivities=["sports"],
            commuteMode="walking",
            outdoorWorkerOrAthlete=True,
            indoorContext=IndoorContext(purifierAvailable=False, ventilationConstraints=False),
            plannedOutdoorActivity=PlannedOutdoorActivity(
                activity="Outdoor 20 km marathon training run",
                preferredPeriod="morning",
            ),
        )

        provider = MockGroundedPlanProvider()
        scenarios = [
            (38.0, 9.5, 28.0, "low"),
            (78.0, 24.0, 62.0, "moderate"),
            (135.0, 48.0, 110.0, "high"),
            (360.0, 175.0, 290.0, "severe"),
        ]
        for aqi_val, pm25_val, pm10_val, expected_risk in scenarios:
            telem = with_classified_freshness(
                base_telemetry.model_copy(
                    update={
                        "measurements": base_telemetry.measurements.model_copy(
                            update={"aqi": aqi_val, "pm25": pm25_val, "pm10": pm10_val}
                        )
                    }
                )
            )
            policy = evaluate_policy(telem, conflicting_athlete)
            self.assertEqual(policy.riskCategory, expected_risk)
            prompt = build_grounded_prompt(telem, policy, conflicting_athlete, request_id=f"eval-{aqi_val}")
            raw = provider.generate_plan_raw(GroundedPlanInput(telem, conflicting_athlete, policy, prompt))
            validation = validate_ai_plan_output(raw, telem, policy)
            self.assertTrue(validation.valid, f"Failed validation at AQI={aqi_val}: {validation.errors}")
            assert validation.plan is not None
            self.assertGreaterEqual(len(validation.plan.profileDrivers), 1)
            if expected_risk == "severe":
                self.assertIn("indoor", validation.plan.priority.action.lower())

    def test_partial_pm10_missing_disclosed_in_limitations(self) -> None:
        profile = UserProfile(
            household=["adult", "senior"],
            vulnerabilities=["cardiovascular_condition"],
            primaryActivities=["errands"],
            commuteMode="car",
        )
        resp = run_analysis(
            AnalysisRequest(
                locationId="kolkata",
                profile=profile,
                options={"simulateMode": "partial_pm"},  # type: ignore[arg-type]
            )
        )
        self.assertIsNone(resp.telemetry.measurements.pm10)
        self.assertTrue(any("Partial pollutant readings" in lim for lim in resp.limitations))


if __name__ == "__main__":
    unittest.main()
