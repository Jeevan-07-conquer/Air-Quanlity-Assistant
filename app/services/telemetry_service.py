"""Redacted observability metrics (SRD §12 Observability, Prompt 11).

Never logs API secrets or sensitive health-profile details.
"""

from dataclasses import dataclass, field


@dataclass
class RedactedTelemetryStore:
    total_requests: int = 0
    success_count: int = 0
    degraded_count: int = 0
    unavailable_count: int = 0
    provider_failures: int = 0
    validation_failures: int = 0
    repair_attempts: int = 0
    freshness_counts: dict[str, int] = field(
        default_factory=lambda: {"live": 0, "recent": 0, "stale": 0, "unavailable": 0}
    )
    recent_events: list[dict[str, str | int | bool]] = field(default_factory=list)

    def record(
        self,
        *,
        request_id: str,
        location_id: str,
        status: str,
        freshness: str,
        provider_latency_ms: int,
        llm_latency_ms: int,
        provider_failed: bool,
        validation_failed: bool,
        repair_attempted: bool,
    ) -> None:
        self.total_requests += 1
        if status == "success":
            self.success_count += 1
        elif status == "degraded":
            self.degraded_count += 1
        else:
            self.unavailable_count += 1

        if provider_failed:
            self.provider_failures += 1
        if validation_failed:
            self.validation_failures += 1
        if repair_attempted:
            self.repair_attempts += 1

        self.freshness_counts[freshness] = self.freshness_counts.get(freshness, 0) + 1
        self.recent_events.append(
            {
                "requestId": request_id,
                "locationId": location_id,
                "status": status,
                "freshness": freshness,
                "providerLatencyMs": provider_latency_ms,
                "llmLatencyMs": llm_latency_ms,
                "repairAttempted": repair_attempted,
            }
        )
        if len(self.recent_events) > 50:
            self.recent_events = self.recent_events[-50:]

    def snapshot(self) -> dict:
        return {
            "totalRequests": self.total_requests,
            "successCount": self.success_count,
            "degradedCount": self.degraded_count,
            "unavailableCount": self.unavailable_count,
            "providerFailures": self.provider_failures,
            "validationFailures": self.validation_failures,
            "repairAttempts": self.repair_attempts,
            "freshnessDistribution": dict(self.freshness_counts),
        }


OBSERVABILITY = RedactedTelemetryStore()
