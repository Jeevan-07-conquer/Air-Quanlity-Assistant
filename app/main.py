"""Starlette ASGI entry point with API endpoints and production security hardening (SRD Prompts 02, 08, 11)."""

import hmac
import os
from pathlib import Path
from typing import Optional

from app.config.env_loader import load_env_file

load_env_file()

from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from app.config.cities import SUPPORTED_CITIES
from app.config.presets import SAMPLE_PRESETS
from app.lib.rate_limit import SlidingWindowRateLimiter
from app.schemas.analysis import AnalysisRequest
from app.schemas.followup import FollowupRequest
from app.services.analysis_service import run_analysis
from app.services.followup_service import answer_followup_question
from app.services.location_service import search_locations
from app.services.telemetry_service import OBSERVABILITY

STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_REQUEST_BYTES = 32 * 1024  # 32 KB request body guard
RATE_LIMITER = SlidingWindowRateLimiter(max_requests=45, window_seconds=60)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers, HSTS over HTTPS, no-store on APIs, and restrictive CSP."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(self)"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        proto = request.headers.get("x-forwarded-proto", "").lower()
        if request.url.scheme == "https" or proto == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response


def _client_key(request: Request) -> str:
    if os.environ.get("TRUST_PROXY_HEADERS", "false").strip().lower() == "true":
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            first_hop = forwarded.split(",")[0].strip()
            if first_hop:
                return first_hop[:64]
    return request.client.host if request.client else "unknown"


def _exceeds_content_length(request: Request, limit: int) -> bool:
    raw_len = request.headers.get("content-length")
    if not raw_len:
        return False
    try:
        return int(raw_len) > limit
    except ValueError:
        return True


async def healthz(_request: Request):
    return JSONResponse({"status": "ok", "version": "1.0"})


async def index(_request: Request):
    return FileResponse(STATIC_DIR / "index.html")


async def shell_bootstrap(_request: Request):
    return JSONResponse(
        {
            "cities": SUPPORTED_CITIES,
            "presets": SAMPLE_PRESETS,
        }
    )


async def get_locations(request: Request):
    if not RATE_LIMITER.allow(_client_key(request)):
        return JSONResponse(
            {"error": "Rate limit exceeded. Please wait briefly before retrying."},
            status_code=429,
        )

    query = request.query_params.get("query", "")[:80]
    lat_raw = request.query_params.get("lat")
    lon_raw = request.query_params.get("lon")
    lat: Optional[float] = None
    lon: Optional[float] = None

    if lat_raw is not None or lon_raw is not None:
        try:
            lat = float(lat_raw or "")
            lon = float(lon_raw or "")
        except ValueError:
            return JSONResponse({"error": "Invalid latitude or longitude."}, status_code=400)
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return JSONResponse({"error": "Latitude or longitude out of range."}, status_code=400)

    res = search_locations(query=query, lat=lat, lon=lon)
    return JSONResponse(res.model_dump())


async def post_analysis(request: Request):
    if not RATE_LIMITER.allow(_client_key(request)):
        return JSONResponse(
            {"error": "Rate limit exceeded. Please wait briefly before retrying."},
            status_code=429,
        )

    if _exceeds_content_length(request, MAX_REQUEST_BYTES):
        return JSONResponse({"error": "Request body exceeds maximum allowed size."}, status_code=413)

    raw_body = await request.body()
    if len(raw_body) > MAX_REQUEST_BYTES:
        return JSONResponse({"error": "Request body exceeds maximum allowed size."}, status_code=413)

    try:
        payload = await request.json()
        parsed_req = AnalysisRequest.model_validate(payload)
    except ValueError:
        return JSONResponse({"error": "Malformed JSON request body."}, status_code=400)
    except ValidationError as exc:
        return JSONResponse(
            {
                "error": "Invalid analysis request payload.",
                "details": [e["msg"] for e in exc.errors()[:4]],
            },
            status_code=400,
        )

    try:
        analysis = run_analysis(parsed_req)
        return JSONResponse(analysis.model_dump())
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception:
        return JSONResponse(
            {"error": "Unexpected server error while generating analysis."},
            status_code=500,
        )


async def post_followup(request: Request):
    if not RATE_LIMITER.allow(_client_key(request)):
        return JSONResponse(
            {"error": "Rate limit exceeded. Please wait briefly before retrying."},
            status_code=429,
        )

    max_followup_bytes = MAX_REQUEST_BYTES * 2
    if _exceeds_content_length(request, max_followup_bytes):
        return JSONResponse({"error": "Request body exceeds maximum allowed size."}, status_code=413)

    raw_body = await request.body()
    if len(raw_body) > max_followup_bytes:
        return JSONResponse({"error": "Request body exceeds maximum allowed size."}, status_code=413)

    try:
        payload = await request.json()
        parsed_req = FollowupRequest.model_validate(payload)
    except (ValueError, ValidationError):
        return JSONResponse({"error": "Invalid follow-up question request."}, status_code=400)

    try:
        resp = answer_followup_question(parsed_req)
        return JSONResponse(resp.model_dump())
    except Exception:
        return JSONResponse(
            {"error": "Unexpected server error while answering follow-up question."},
            status_code=500,
        )


async def get_observability(request: Request):
    required_token = os.environ.get("OBSERVABILITY_TOKEN", "").strip()
    is_prod = os.environ.get("APP_ENV", "development").strip().lower() == "production"

    if is_prod and not required_token:
        return JSONResponse({"error": "Not found."}, status_code=404)

    if required_token:
        auth = request.headers.get("authorization", "")
        expected = f"Bearer {required_token}"
        if not hmac.compare_digest(auth, expected):
            return JSONResponse({"error": "Unauthorized."}, status_code=401)

    return JSONResponse(OBSERVABILITY.snapshot())


routes = [
    Route("/healthz", healthz, methods=["GET"]),
    Route("/api/shell-bootstrap", shell_bootstrap, methods=["GET"]),
    Route("/api/locations", get_locations, methods=["GET"]),
    Route("/api/analysis", post_analysis, methods=["POST"]),
    Route("/api/followup", post_followup, methods=["POST"]),
    Route("/api/observability", get_observability, methods=["GET"]),
    Route("/", index, methods=["GET"]),
    Mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static"),
]

app = Starlette(debug=False, routes=routes)
app.add_middleware(SecurityHeadersMiddleware)

allowed_hosts_raw = os.environ.get("ALLOWED_HOSTS", "").strip()
if allowed_hosts_raw:
    allowed_hosts = [h.strip() for h in allowed_hosts_raw.split(",") if h.strip()]
    if allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
