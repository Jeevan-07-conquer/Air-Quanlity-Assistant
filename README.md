# Urban Air Quality Assistant

A grounded Generative AI web application helping families and communities in polluted Indian cities (**Delhi NCR, Noida, Mumbai, Kolkata**) navigate winter smog and urban air pollution with verifiable live telemetry and practical daily action plans.

## Core Capabilities
- **Live Real-Time Environmental Data (Never AI-Invented):** Retrieves station-level `AQI`, `PM2.5`, and `PM10` from the WAQI / AQICN API (`app/services/providers/waqi_adapter.py`) with explicit source attribution, `observedAt`/`retrievedAt` timestamps, and deterministic freshness classification (`live`, `recent`, `stale`, `unavailable`).
- **Low-Emission Daily Routines & Activity Planning:** Builds morning, afternoon, evening, and night plans tailored to household composition (toddlers/children, seniors, pregnant members, commuters, outdoor athletes/workers).
- **Indoor Air Quality Guidance & Control:** Provides optimal HEPA air purifier placement, room sealing, kitchen smoke mitigation, deterministic open-window safety gates, and evidence-based guidance on indoor plants.
- **Sustainable Alternatives with Justified Impact:** Recommends enclosed public transit, carpooling, and combining multiple trips, explaining the direct exposure and emissions impact alongside trade-offs.
- **Grounded Interactive Follow-Up Q&A:** Lets users ask follow-up questions (`POST /api/followup`) strictly constrained to verified station data, safety rules, and the active plan.
- **Evaluator Sample Profiles:** Includes 4 one-click labeled sample profiles for immediate testing.

## Architecture (Dual-Level Truth Model)
1. **Verified Telemetry Layer (`environment_service.py`):** Server-side provider fetch, range/unit validation, TTL caching by city, and freshness grading.
2. **Deterministic Policy Engine (`policy_service.py`):** Versioned rules (`policyVersion: 1.0.0`) enforcing risk tiers, vulnerability escalation, and hard constraints (e.g., `ventilation_prohibited`) prior to any LLM call.
3. **Grounded AI & Safety Validator (`llm_service.py`, `validation_service.py`, `fallback_service.py`):** Structured JSON generation via `google-genai` with Flash model fallback, single repair retry, strict metric-equality and safety validation, and deterministic fallback when AI is unavailable.

## Security & Accessibility
- **Security:** Server-only API secrets, allowlisted cities & provider URLs, strict `Content-Security-Policy` (`script-src 'self'; style-src 'self'`), `HSTS`, `X-Frame-Options: DENY`, `Cache-Control: no-store` on `/api/*`, proxy-aware rate limiting (`45 req/min`), request size caps, and zero server persistence of health sensitivities.
- **Accessibility (WCAG 2.2 AA):** Semantic landmarks (`<header>`, `<nav>`, `<main>`, `<footer>`), skip link, `aria-live="polite"`, `aria-busy`, keyboard carousel navigation, `>= 44px` touch targets, and `prefers-reduced-motion` support.

## Run Locally
```powershell
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-server-header
```

## Run Automated Tests
```powershell
python -m unittest discover -s tests -v
```
