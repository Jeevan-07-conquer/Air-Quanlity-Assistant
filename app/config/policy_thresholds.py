"""Versioned deterministic policy thresholds and safety copy (SRD FR-05, FR-06, §10.4).

Thresholds are separated from UI and LLM logic. Never silently combine incompatible AQI standards.
"""

POLICY_VERSION = "1.0.0"
ANALYSIS_VERSION = "1.0"
AQI_STANDARD = "US-EPA (WAQI)"

# Freshness windows in minutes (FR-05)
LIVE_MAX_MINUTES = 30
RECENT_MAX_MINUTES = 120
STALE_MAX_MINUTES = 720

# US-EPA / WAQI-normalized AQI cutoffs (inclusive upper bounds)
AQI_THRESHOLDS = {
    "low": 50.0,
    "moderate": 100.0,
    "high": 150.0,
    "very_high": 250.0,
    # > 250 => severe
}

# PM2.5 (µg/m³) secondary guardrails when AQI is missing or PM2.5 indicates higher concern
PM25_THRESHOLDS = {
    "low": 12.0,
    "moderate": 35.4,
    "high": 55.4,
    "very_high": 150.4,
}

PERSISTENT_SAFETY_NOTICE = (
    "This tool provides general air-quality guidance, not medical diagnosis or treatment. "
    "Follow official public-health guidance and contact a qualified clinician for health concerns. "
    "Seek urgent help for severe breathing difficulty, chest pain, confusion, or other emergency symptoms."
)

TELEMETRY_CACHE_TTL_SECONDS = 180
ANALYSIS_CACHE_TTL_SECONDS = 300
