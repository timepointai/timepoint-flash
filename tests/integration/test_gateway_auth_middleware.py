"""Integration tests for the edge GatewayAuthMiddleware (API-4).

Covers the four configurations we care about:

* Open mode (no FLASH_SERVICE_KEY, no GATEWAY_SIGNING_SECRET) — all requests
  pass.
* Signed-only mode (REQUIRE_SIGNED_GATEWAY=True) — unsigned requests 403.
* Dual mode (GATEWAY_SIGNING_SECRET set, legacy allowed) — signed requests
  trusted, legacy X-Service-Key requests allowed as system calls but cannot
  impersonate users.
* Tamper protection — modifying X-User-Id after signing must 403.
"""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.auth.gateway_signing import (
    SIGNATURE_VERSION,
    build_canonical_string,
    compute_signature,
)


def _make_signature(
    secret: str, method: str, path: str, user_id: str, ts: int
) -> tuple[str, str]:
    canonical = build_canonical_string(method, path, user_id, str(ts))
    sig = compute_signature(secret, canonical)
    return str(ts), f"{SIGNATURE_VERSION}={sig}"


def _build_app(monkeypatch: pytest.MonkeyPatch, **env: str) -> FastAPI:
    """Build a minimal FastAPI app wired with our GatewayAuthMiddleware.

    Sets the given env vars, clears the Settings lru_cache, then wires the
    middleware against a bare FastAPI so the test runs fast and doesn't pull
    in the full Flash app (DB, providers, etc).
    """
    # Clear out any pre-existing auth knobs that might be in the environment.
    for key in (
        "FLASH_SERVICE_KEY",
        "GATEWAY_SIGNING_SECRET",
        "REQUIRE_SIGNED_GATEWAY",
        "ALLOW_LEGACY_SERVICE_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    # Rebuild the cached settings against the new env. The middleware reads
    # get_settings() fresh on every dispatch, so clearing the cache is enough
    # — no module reload needed (which would trip over FastAPI's lifespan).
    import app.config as config_module

    config_module.get_settings.cache_clear()

    from app.main import GatewayAuthMiddleware

    app = FastAPI()
    app.add_middleware(GatewayAuthMiddleware)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/v1/probe")
    async def probe(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "gateway_verified": bool(
                    getattr(request.state, "gateway_verified", False)
                ),
                "x_user_id": request.headers.get("X-User-Id")
                or request.headers.get("X-User-ID"),
            }
        )

    return app


class TestOpenMode:
    """When no keys are configured at all, every request flows through."""

    def test_open_mode_allows_everything(self, monkeypatch: pytest.MonkeyPatch):
        app = _build_app(monkeypatch)
        client = TestClient(app)

        resp = client.get("/api/v1/probe")
        assert resp.status_code == 200
        body = resp.json()
        assert body["gateway_verified"] is False


class TestLegacyServiceKey:
    def test_valid_service_key_allowed_but_not_user_verified(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        app = _build_app(
            monkeypatch,
            FLASH_SERVICE_KEY="svc-abc",
            ALLOW_LEGACY_SERVICE_KEY="true",
        )
        client = TestClient(app)

        resp = client.get(
            "/api/v1/probe",
            headers={"X-Service-Key": "svc-abc", "X-User-Id": "u-attacker"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # Request passes middleware but is NOT flagged as gateway-verified —
        # get_current_user will drop the X-User-Id claim.
        assert body["gateway_verified"] is False

    def test_invalid_service_key_rejected(self, monkeypatch: pytest.MonkeyPatch):
        app = _build_app(monkeypatch, FLASH_SERVICE_KEY="svc-abc")
        client = TestClient(app)

        resp = client.get(
            "/api/v1/probe",
            headers={"X-Service-Key": "wrong"},
        )
        assert resp.status_code == 403

    def test_missing_service_key_rejected(self, monkeypatch: pytest.MonkeyPatch):
        app = _build_app(monkeypatch, FLASH_SERVICE_KEY="svc-abc")
        client = TestClient(app)

        resp = client.get("/api/v1/probe")
        assert resp.status_code == 403

    def test_health_always_open_even_with_service_key(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        app = _build_app(monkeypatch, FLASH_SERVICE_KEY="svc-abc")
        client = TestClient(app)

        resp = client.get("/health")
        assert resp.status_code == 200


class TestSignedGateway:
    SECRET = "gw-signing-secret"

    def test_valid_signature_marks_request_verified(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        app = _build_app(monkeypatch, GATEWAY_SIGNING_SECRET=self.SECRET)
        client = TestClient(app)

        ts, sig = _make_signature(
            self.SECRET, "GET", "/api/v1/probe", "u-1", int(time.time())
        )
        resp = client.get(
            "/api/v1/probe",
            headers={
                "X-User-Id": "u-1",
                "X-Gateway-Timestamp": ts,
                "X-Gateway-Signature": sig,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["gateway_verified"] is True
        assert body["x_user_id"] == "u-1"

    def test_tampered_user_id_rejected(self, monkeypatch: pytest.MonkeyPatch):
        """Sign for u-1, send header as u-attacker — must 403."""
        app = _build_app(monkeypatch, GATEWAY_SIGNING_SECRET=self.SECRET)
        client = TestClient(app)

        ts, sig = _make_signature(
            self.SECRET, "GET", "/api/v1/probe", "u-1", int(time.time())
        )
        resp = client.get(
            "/api/v1/probe",
            headers={
                "X-User-Id": "u-attacker",  # ← mismatched
                "X-Gateway-Timestamp": ts,
                "X-Gateway-Signature": sig,
            },
        )
        assert resp.status_code == 403
        assert "Invalid gateway signature" in resp.text

    def test_stale_timestamp_rejected(self, monkeypatch: pytest.MonkeyPatch):
        app = _build_app(monkeypatch, GATEWAY_SIGNING_SECRET=self.SECRET)
        client = TestClient(app)

        stale = int(time.time()) - 10_000
        ts, sig = _make_signature(self.SECRET, "GET", "/api/v1/probe", "u-1", stale)
        resp = client.get(
            "/api/v1/probe",
            headers={
                "X-User-Id": "u-1",
                "X-Gateway-Timestamp": ts,
                "X-Gateway-Signature": sig,
            },
        )
        assert resp.status_code == 403

    def test_require_signed_rejects_legacy_key(self, monkeypatch: pytest.MonkeyPatch):
        app = _build_app(
            monkeypatch,
            FLASH_SERVICE_KEY="svc-abc",
            GATEWAY_SIGNING_SECRET=self.SECRET,
            REQUIRE_SIGNED_GATEWAY="true",
        )
        client = TestClient(app)

        resp = client.get(
            "/api/v1/probe",
            headers={"X-Service-Key": "svc-abc", "X-User-Id": "u-1"},
        )
        assert resp.status_code == 403
        assert "Gateway signature required" in resp.text

    def test_require_signed_accepts_valid_signature(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        app = _build_app(
            monkeypatch,
            FLASH_SERVICE_KEY="svc-abc",
            GATEWAY_SIGNING_SECRET=self.SECRET,
            REQUIRE_SIGNED_GATEWAY="true",
        )
        client = TestClient(app)

        ts, sig = _make_signature(
            self.SECRET, "GET", "/api/v1/probe", "u-1", int(time.time())
        )
        resp = client.get(
            "/api/v1/probe",
            headers={
                "X-User-Id": "u-1",
                "X-Gateway-Timestamp": ts,
                "X-Gateway-Signature": sig,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["gateway_verified"] is True
