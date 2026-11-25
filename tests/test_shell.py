"""Smoke tests for application shell, static assets, and HTTP endpoints (no asyncio socketpair dependency)."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from starlette.requests import Request

from app.config.env_loader import load_env_file

from app.main import (
    STATIC_DIR,
    SecurityHeadersMiddleware,
    get_locations,
    get_observability,
    healthz,
    index,
    post_analysis,
    post_followup,
    shell_bootstrap,
)


def run_coro_sync(coro):
    """Drive a non-blocking ASGI coroutine synchronously in restricted environments."""
    try:
        while True:
            coro.send(None)
    except StopIteration as stop:
        return stop.value


def make_request(
    path: str = "/",
    method: str = "GET",
    query_string: str = "",
    body: bytes = b"",
    client_host: str = "127.0.0.1",
    extra_headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    headers = [(b"host", b"testserver"), (b"content-type", b"application/json")]
    if extra_headers:
        headers.extend(extra_headers)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": query_string.encode("ascii"),
        "headers": headers,
        "client": (client_host, 12345),
        "server": ("testserver", 80),
    }
    return Request(scope, receive)


class TestApplicationShellAndRoutes(unittest.TestCase):
    def test_healthz_endpoint(self) -> None:
        resp = run_coro_sync(healthz(make_request("/healthz")))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.body)["status"], "ok")

    def test_shell_bootstrap_lists_cities_and_presets(self) -> None:
        resp = run_coro_sync(shell_bootstrap(make_request("/api/shell-bootstrap")))
        self.assertEqual(resp.status_code, 200)
        payload = json.loads(resp.body)
        city_ids = {c["id"] for c in payload["cities"]}
        self.assertTrue({"delhi", "noida", "mumbai", "kolkata"}.issubset(city_ids))
        self.assertGreaterEqual(len(payload["presets"]), 4)
        for preset in payload["presets"]:
            self.assertEqual(preset["badge"], "Sample profile")
            self.assertIn("profile", preset)

    def test_static_shell_and_design_tokens_exist(self) -> None:
        resp = run_coro_sync(index(make_request("/")))
        self.assertEqual(resp.status_code, 200)
        html_text = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn("Urban Air Quality Assistant", html_text)
        self.assertIn("Skip to main content", html_text)
        self.assertIn("Safety notice:", html_text)

        tokens_text = (STATIC_DIR / "styles" / "tokens.css").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion: reduce", tokens_text)
        self.assertIn("--color-bg-canvas", tokens_text)
        self.assertTrue((STATIC_DIR / "js" / "components" / "dashboardViews.js").exists())
        self.assertTrue((STATIC_DIR / "js" / "components" / "profileForm.js").exists())

    def test_locations_and_observability_endpoints(self) -> None:
        loc_resp = run_coro_sync(get_locations(make_request("/api/locations", query_string="query=delhi")))
        self.assertEqual(loc_resp.status_code, 200)
        loc_data = json.loads(loc_resp.body)
        self.assertEqual(loc_data["resolutionStatus"], "matched")
        self.assertEqual(loc_data["matches"][0]["id"], "delhi")

        obs_resp = run_coro_sync(get_observability(make_request("/api/observability")))
        self.assertEqual(obs_resp.status_code, 200)
        self.assertIn("totalRequests", json.loads(obs_resp.body))

        with patch.dict(os.environ, {"APP_ENV": "production", "OBSERVABILITY_TOKEN": ""}):
            hidden_obs = run_coro_sync(get_observability(make_request("/api/observability")))
            self.assertEqual(hidden_obs.status_code, 404)

        with patch.dict(os.environ, {"APP_ENV": "production", "OBSERVABILITY_TOKEN": "secret-123"}):
            unauth_obs = run_coro_sync(get_observability(make_request("/api/observability")))
            self.assertEqual(unauth_obs.status_code, 401)
            auth_obs = run_coro_sync(
                get_observability(
                    make_request("/api/observability", extra_headers=[(b"authorization", b"Bearer secret-123")])
                )
            )
            self.assertEqual(auth_obs.status_code, 200)

    def test_post_analysis_route_and_oversized_body_guard(self) -> None:
        valid_body = json.dumps(
            {
                "locationId": "delhi",
                "profile": {
                    "household": ["adult"],
                    "primaryActivities": ["commute"],
                    "commuteMode": "public_transit",
                },
            }
        ).encode("utf-8")
        with patch.dict(os.environ, {"TELEMETRY_MODE": "fixture", "WAQI_API_TOKEN": "", "GEMINI_API_KEY": ""}):
            resp = run_coro_sync(post_analysis(make_request("/api/analysis", method="POST", body=valid_body)))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.body)
        self.assertEqual(data["telemetry"]["location"]["id"], "delhi")
        self.assertEqual(len(data["plan"]["timeline"]), 4)

        huge_body = b"x" * (33 * 1024)
        huge_resp = run_coro_sync(post_analysis(make_request("/api/analysis", method="POST", body=huge_body)))
        self.assertEqual(huge_resp.status_code, 413)

        followup_body = json.dumps(
            {
                "question": "When is it safe to open windows?",
                "telemetry": data["telemetry"],
                "policy": data["policy"],
                "profile": {
                    "household": ["adult"],
                    "primaryActivities": ["commute"],
                    "commuteMode": "public_transit",
                },
                "plan": data["plan"],
            }
        ).encode("utf-8")
        with patch.dict(os.environ, {"TELEMETRY_MODE": "fixture", "WAQI_API_TOKEN": "", "GEMINI_API_KEY": ""}):
            f_resp = run_coro_sync(post_followup(make_request("/api/followup", method="POST", body=followup_body)))
        self.assertEqual(f_resp.status_code, 200)
        f_data = json.loads(f_resp.body)
        self.assertIn("answer", f_data)
        self.assertIn("nextStep", f_data)

    def test_security_headers_middleware_adds_csp(self) -> None:
        middleware = SecurityHeadersMiddleware(app=None)  # type: ignore[arg-type]

        async def next_call(_req):
            return run_coro_sync(healthz(make_request("/healthz")))

        resp = run_coro_sync(middleware.dispatch(make_request("/healthz"), next_call))
        self.assertEqual(resp.headers["X-Frame-Options"], "DENY")
        self.assertEqual(resp.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(resp.headers["Cross-Origin-Opener-Policy"], "same-origin")
        csp = resp.headers["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("style-src 'self'", csp)
        self.assertNotIn("unsafe-inline", csp)

        https_req = make_request("/api/locations", extra_headers=[(b"x-forwarded-proto", b"https")])
        https_resp = run_coro_sync(middleware.dispatch(https_req, next_call))
        self.assertIn("max-age=31536000", https_resp.headers["Strict-Transport-Security"])
        self.assertEqual(https_resp.headers["Cache-Control"], "no-store")

    def test_frontend_has_no_inline_styles_and_valid_aria_semantics(self) -> None:
        static_files = list(STATIC_DIR.rglob("*.js")) + [STATIC_DIR / "index.html"]
        for path in static_files:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("style=", text, f"Inline style attribute found in {path.name}")
            self.assertNotIn('role="tab"', text, f"Orphaned ARIA tab role found in {path.name}")

        landing_js = (STATIC_DIR / "js" / "components" / "landing.js").read_text(encoding="utf-8")
        self.assertIn('role="presentation"', landing_js)
        main_js = (STATIC_DIR / "js" / "main.js").read_text(encoding="utf-8")
        self.assertIn("aria-busy", main_js)

    def test_env_loader_and_gitignore(self) -> None:
        root = Path(__file__).resolve().parent.parent
        gitignore = (root / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".env", gitignore)

        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text('TEST_UAQA_KEY="hello-world"\nTEST_UAQA_EXISTING=from-file\n', encoding="utf-8")
            os.environ["TEST_UAQA_EXISTING"] = "from-env"
            os.environ.pop("TEST_UAQA_KEY", None)
            try:
                load_env_file(env_file)
                self.assertEqual(os.environ.get("TEST_UAQA_KEY"), "hello-world")
                self.assertEqual(os.environ.get("TEST_UAQA_EXISTING"), "from-env")
            finally:
                os.environ.pop("TEST_UAQA_KEY", None)
                os.environ.pop("TEST_UAQA_EXISTING", None)


if __name__ == "__main__":
    unittest.main()
