"""Unit tests for the Flash MCP server.

Exercises:

- Bearer-token verification against ``FLASH_MCP_BEARER_TOKENS`` env tokens
  and via the Gateway introspection fallback (monkeypatched).
- The ``BearerAuthMiddleware`` ASGI middleware — 401 paths, CORS preflight,
  happy-path ``user_id`` propagation.
- Extraction of the Bearer token from ASGI headers.
- The ``tp_flash_generate`` tool body — validation, owner propagation, and
  that a timepoint row is created and a background task is scheduled.  The
  actual generation pipeline is monkeypatched so no real LLM calls happen.
- HTTP-level protection: a real ``TestClient`` against the full FastAPI app
  confirms that requests to ``/mcp/`` without a Bearer header return 401
  and that mounting MCP does not break the ``/health`` endpoint.
"""

from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

# Ensure we're in test mode before any app imports that read env vars
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEBUG", "true")

from app.middleware.bearer_auth import (  # noqa: E402
    BearerAuthMiddleware,
    _parse_static_tokens,
    current_bearer_user,
    extract_bearer_token,
    get_current_bearer_user,
    verify_bearer_token,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    """Clean relevant env vars for every test."""
    monkeypatch.delenv("FLASH_MCP_BEARER_TOKENS", raising=False)
    monkeypatch.delenv("GATEWAY_INTERNAL_URL", raising=False)
    monkeypatch.delenv("GATEWAY_SERVICE_KEY", raising=False)
    yield


# ============================================================================
# _parse_static_tokens
# ============================================================================


@pytest.mark.fast
class TestParseStaticTokens:
    def test_empty_env_returns_empty_dict(self):
        assert _parse_static_tokens() == {}

    def test_single_token_without_userid(self, monkeypatch):
        monkeypatch.setenv("FLASH_MCP_BEARER_TOKENS", "static-abc123")
        parsed = _parse_static_tokens()
        assert list(parsed.keys()) == ["static-abc123"]
        assert parsed["static-abc123"].startswith("bearer-")

    def test_token_with_explicit_userid(self, monkeypatch):
        monkeypatch.setenv("FLASH_MCP_BEARER_TOKENS", "tok-1:user-one")
        parsed = _parse_static_tokens()
        assert parsed == {"tok-1": "user-one"}

    def test_whitespace_and_empty_entries_tolerated(self, monkeypatch):
        monkeypatch.setenv("FLASH_MCP_BEARER_TOKENS", " , tok-1:user1 , , tok-2 ,")
        parsed = _parse_static_tokens()
        assert parsed["tok-1"] == "user1"
        assert "tok-2" in parsed

    def test_multiple_tokens_mixed_forms(self, monkeypatch):
        monkeypatch.setenv("FLASH_MCP_BEARER_TOKENS", "tok-1:user1,tok-2,tok-3:user3")
        parsed = _parse_static_tokens()
        assert parsed["tok-1"] == "user1"
        assert parsed["tok-3"] == "user3"
        assert parsed["tok-2"].startswith("bearer-")


# ============================================================================
# verify_bearer_token
# ============================================================================


@pytest.mark.fast
class TestVerifyBearerToken:
    @pytest.mark.asyncio
    async def test_empty_token_returns_none(self):
        assert await verify_bearer_token("") is None

    @pytest.mark.asyncio
    async def test_unknown_token_returns_none(self):
        assert await verify_bearer_token("not-configured") is None

    @pytest.mark.asyncio
    async def test_static_token_without_userid(self, monkeypatch):
        monkeypatch.setenv("FLASH_MCP_BEARER_TOKENS", "static-abc123")
        uid = await verify_bearer_token("static-abc123")
        assert uid is not None
        assert uid.startswith("bearer-")

    @pytest.mark.asyncio
    async def test_static_token_with_userid(self, monkeypatch):
        monkeypatch.setenv("FLASH_MCP_BEARER_TOKENS", "tok-1:user-one, tok-2:user-two")
        assert await verify_bearer_token("tok-1") == "user-one"
        assert await verify_bearer_token("tok-2") == "user-two"

    @pytest.mark.asyncio
    async def test_non_gateway_prefix_skips_gateway_call(self, monkeypatch):
        """Tokens that don't look like Gateway keys never hit the Gateway."""
        called = {"flag": False}

        async def fake_gateway(token):
            called["flag"] = True
            return "user-from-gateway"

        monkeypatch.setattr("app.middleware.bearer_auth._verify_via_gateway", fake_gateway)
        # plain token that doesn't start with tp_gw_ or tp_org_ should
        # not trigger the gateway call
        result = await verify_bearer_token("plain-token")
        assert result is None
        assert called["flag"] is False

    @pytest.mark.asyncio
    async def test_gateway_prefix_routes_to_gateway(self, monkeypatch):
        async def fake_gateway(token):
            assert token == "tp_gw_alice_key"
            return "alice"

        monkeypatch.setattr("app.middleware.bearer_auth._verify_via_gateway", fake_gateway)
        assert await verify_bearer_token("tp_gw_alice_key") == "alice"

    @pytest.mark.asyncio
    async def test_gateway_prefix_unknown_returns_none(self, monkeypatch):
        async def fake_gateway(token):
            return None

        monkeypatch.setattr("app.middleware.bearer_auth._verify_via_gateway", fake_gateway)
        assert await verify_bearer_token("tp_gw_revoked") is None

    @pytest.mark.asyncio
    async def test_org_prefix_routes_to_gateway(self, monkeypatch):
        async def fake_gateway(token):
            assert token == "tp_org_acme_key"
            return "acme-org-user"

        monkeypatch.setattr("app.middleware.bearer_auth._verify_via_gateway", fake_gateway)
        assert await verify_bearer_token("tp_org_acme_key") == "acme-org-user"

    @pytest.mark.asyncio
    async def test_static_token_takes_precedence(self, monkeypatch):
        """A token configured in env should never hit the Gateway."""
        monkeypatch.setenv("FLASH_MCP_BEARER_TOKENS", "tp_gw_local:local-dev-user")

        async def fake_gateway(token):
            raise AssertionError("Gateway should not be called for static tokens")

        monkeypatch.setattr("app.middleware.bearer_auth._verify_via_gateway", fake_gateway)
        assert await verify_bearer_token("tp_gw_local") == "local-dev-user"


# ============================================================================
# _verify_via_gateway
# ============================================================================


@pytest.mark.fast
class TestVerifyViaGateway:
    @pytest.mark.asyncio
    async def test_missing_config_returns_none(self):
        from app.middleware.bearer_auth import _verify_via_gateway

        # No GATEWAY_INTERNAL_URL / GATEWAY_SERVICE_KEY set — should bail out
        # without raising.
        assert await _verify_via_gateway("tp_gw_xyz") is None

    @pytest.mark.asyncio
    async def test_200_returns_user_id(self, monkeypatch):
        from app.middleware.bearer_auth import _verify_via_gateway

        monkeypatch.setenv("GATEWAY_INTERNAL_URL", "https://gateway.example.com")
        monkeypatch.setenv("GATEWAY_SERVICE_KEY", "s3cret")

        class FakeResponse:
            status_code = 200

            def json(self):
                return {"user_id": "alice", "email": "a@b.co", "tier": "pro"}

        class FakeClient:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            async def post(self, url, json, headers):
                assert url == "https://gateway.example.com/internal/auth/validate-key"
                assert headers["X-Service-Key"] == "s3cret"
                assert json == {"key": "tp_gw_xyz"}
                return FakeResponse()

        monkeypatch.setattr("app.middleware.bearer_auth.httpx.AsyncClient", FakeClient)
        assert await _verify_via_gateway("tp_gw_xyz") == "alice"

    @pytest.mark.asyncio
    async def test_non_200_returns_none(self, monkeypatch):
        from app.middleware.bearer_auth import _verify_via_gateway

        monkeypatch.setenv("GATEWAY_INTERNAL_URL", "https://gateway.example.com")
        monkeypatch.setenv("GATEWAY_SERVICE_KEY", "s3cret")

        class FakeResponse:
            status_code = 401

            def json(self):
                return {"detail": "Invalid or revoked key"}

        class FakeClient:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            async def post(self, *a, **kw):
                return FakeResponse()

        monkeypatch.setattr("app.middleware.bearer_auth.httpx.AsyncClient", FakeClient)
        assert await _verify_via_gateway("tp_gw_revoked") is None

    @pytest.mark.asyncio
    async def test_network_error_returns_none(self, monkeypatch):
        import httpx

        from app.middleware.bearer_auth import _verify_via_gateway

        monkeypatch.setenv("GATEWAY_INTERNAL_URL", "https://gateway.example.com")
        monkeypatch.setenv("GATEWAY_SERVICE_KEY", "s3cret")

        class FakeClient:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            async def post(self, *a, **kw):
                raise httpx.ConnectError("boom")

        monkeypatch.setattr("app.middleware.bearer_auth.httpx.AsyncClient", FakeClient)
        assert await _verify_via_gateway("tp_gw_xyz") is None


# ============================================================================
# extract_bearer_token
# ============================================================================


@pytest.mark.fast
class TestExtractBearerToken:
    def test_valid_bearer(self):
        headers = [(b"authorization", b"Bearer abc.def.ghi")]
        assert extract_bearer_token(headers) == "abc.def.ghi"

    def test_case_insensitive_scheme(self):
        headers = [(b"authorization", b"BEARER abc123")]
        assert extract_bearer_token(headers) == "abc123"

    def test_missing_header(self):
        assert extract_bearer_token([]) is None

    def test_non_bearer_scheme(self):
        headers = [(b"authorization", b"Basic dXNlcjpwYXNz")]
        assert extract_bearer_token(headers) is None

    def test_bearer_with_no_token(self):
        headers = [(b"authorization", b"Bearer ")]
        assert extract_bearer_token(headers) is None

    def test_authorization_header_case_insensitive(self):
        headers = [(b"Authorization", b"Bearer xyz")]
        assert extract_bearer_token(headers) == "xyz"


# ============================================================================
# BearerAuthMiddleware — ASGI-level behavior
# ============================================================================


def _echo_app():
    """Minimal ASGI app that returns the captured user_id as JSON."""

    async def app(scope, receive, send):
        if scope["type"] != "http":
            return
        user = get_current_bearer_user()
        response = JSONResponse({"user": user})
        await response(scope, receive, send)

    return app


@pytest.fixture
def middleware_app():
    """FastAPI app wrapping the echo app behind BearerAuthMiddleware."""
    app = FastAPI()
    app.mount("/mcp", BearerAuthMiddleware(_echo_app()))
    return app


@pytest.mark.fast
class TestBearerAuthMiddleware:
    def test_missing_header_returns_401(self, middleware_app):
        client = TestClient(middleware_app)
        response = client.get("/mcp/")
        assert response.status_code == 401
        body = response.json()
        assert body["error"] == "Unauthorized"
        assert "Missing Authorization" in body["message"]
        assert response.headers.get("www-authenticate", "").startswith("Bearer")

    def test_invalid_token_returns_401(self, middleware_app):
        client = TestClient(middleware_app)
        response = client.get("/mcp/", headers={"Authorization": "Bearer not-a-real-token"})
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    def test_valid_static_token_lets_request_through(self, middleware_app, monkeypatch):
        monkeypatch.setenv("FLASH_MCP_BEARER_TOKENS", "static-xyz:svc-account")
        client = TestClient(middleware_app)
        response = client.get("/mcp/", headers={"Authorization": "Bearer static-xyz"})
        assert response.status_code == 200
        assert response.json() == {"user": "svc-account"}

    def test_options_preflight_bypasses_auth(self, middleware_app):
        client = TestClient(middleware_app)
        response = client.options("/mcp/")
        # No 401 — the preflight is allowed through.  Depending on how the
        # sub-app responds it may be 200/204/405, but NOT 401.
        assert response.status_code != 401

    def test_non_bearer_scheme_returns_401(self, middleware_app):
        client = TestClient(middleware_app)
        response = client.get("/mcp/", headers={"Authorization": "Basic dXNlcjpwYXNz"})
        assert response.status_code == 401

    def test_gateway_prefix_without_config_returns_401(self, middleware_app):
        """tp_gw_* tokens need GATEWAY_INTERNAL_URL+GATEWAY_SERVICE_KEY set."""
        client = TestClient(middleware_app)
        response = client.get("/mcp/", headers={"Authorization": "Bearer tp_gw_notconfigured"})
        assert response.status_code == 401


# ============================================================================
# tp_flash_generate tool body
# ============================================================================


class _FakeTimepoint:
    """Minimal stand-in for Timepoint that behaves well with async SQLAlchemy mocks."""

    _counter = 0

    def __init__(self, query, status):
        _FakeTimepoint._counter += 1
        self.id = f"tp_test_{_FakeTimepoint._counter:03d}"
        self.slug = query.replace(" ", "-").lower()[:40]
        self.query = query
        self.status = status
        self.user_id = None
        self.visibility = None


class _FakeSession:
    """Minimal async-session stand-in for Timepoint row creation."""

    def __init__(self):
        self.added: list = []

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        return None

    async def refresh(self, obj):
        return None


class _FakeSessionCM:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *a):
        return None


@pytest.fixture
def _stub_generation(monkeypatch):
    """Patch DB + pipeline so tp_flash_generate doesn't hit anything real."""
    session = _FakeSession()

    def fake_get_session():
        return _FakeSessionCM(session)

    async def fake_run_generation(*args, **kwargs):
        return None

    # Timepoint.create is a classmethod — patch via a proxy that returns
    # our fake.  The tool imports Timepoint locally so we patch the model
    # module directly.
    import app.models as models_mod

    real_create = models_mod.Timepoint.create

    def fake_create(cls, query, **kwargs):
        return _FakeTimepoint(query, kwargs.get("status"))

    monkeypatch.setattr(
        models_mod.Timepoint,
        "create",
        classmethod(fake_create),
    )
    monkeypatch.setattr("app.api.v1.timepoints.run_generation_task", fake_run_generation)
    monkeypatch.setattr("app.database.get_session", fake_get_session)
    # The tool imports get_session inside the function body using
    # ``from app.database import get_session``, so patching the attribute on
    # the module is enough.

    yield session

    # restore create
    monkeypatch.setattr(models_mod.Timepoint, "create", real_create)


@pytest.fixture
def tool_callable():
    """Extract the underlying async function from the FastMCP tool wrapper.

    FastMCP decorators keep the original function accessible as ``.fn``.
    """
    from app.mcp_server import tp_flash_generate

    if hasattr(tp_flash_generate, "fn"):
        return tp_flash_generate.fn
    return tp_flash_generate


@pytest.mark.fast
class TestTpFlashGenerate:
    @pytest.mark.asyncio
    async def test_requires_query(self, _stub_generation, tool_callable):
        result = await tool_callable(query="")
        assert "error" in result
        assert "query" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_query_too_short(self, _stub_generation, tool_callable):
        result = await tool_callable(query="ab")
        assert "error" in result
        assert "3 characters" in result["error"]

    @pytest.mark.asyncio
    async def test_query_too_long(self, _stub_generation, tool_callable):
        result = await tool_callable(query="x" * 501)
        assert "error" in result
        assert "500 characters" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_preset(self, _stub_generation, tool_callable):
        result = await tool_callable(query="rome 50 BCE", preset="ludicrous")
        assert "error" in result
        assert "preset" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_visibility(self, _stub_generation, tool_callable):
        result = await tool_callable(query="rome 50 BCE", visibility="hidden")
        assert "error" in result
        assert "visibility" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_model_policy(self, _stub_generation, tool_callable):
        result = await tool_callable(query="rome 50 BCE", model_policy="proprietary")
        assert "error" in result
        assert "model_policy" in result["error"]

    @pytest.mark.asyncio
    async def test_happy_path_creates_timepoint(self, _stub_generation, tool_callable):
        result = await tool_callable(query="signing of the declaration", preset="balanced")
        assert "error" not in result, result
        assert result["id"].startswith("tp_test_")
        assert result["status"] == "processing"
        assert result["status_url"] == f"/api/v1/timepoints/{result['id']}"
        assert result["query"] == "signing of the declaration"
        assert result["preset"] == "balanced"
        assert result["generate_image"] is False
        # A timepoint row was added to the stub session
        assert len(_stub_generation.added) == 1

    @pytest.mark.asyncio
    async def test_owner_from_bearer_context(self, _stub_generation, tool_callable):
        token = current_bearer_user.set("user_abc")
        try:
            result = await tool_callable(query="rome 50 BCE")
        finally:
            current_bearer_user.reset(token)

        assert "error" not in result, result
        assert result["owner_id"] == "user_abc"

    @pytest.mark.asyncio
    async def test_default_owner_is_anonymous(self, _stub_generation, tool_callable):
        # No contextvar set → anonymous fallback.
        result = await tool_callable(query="rome 50 BCE")
        assert result["owner_id"] == "mcp-anonymous"

    @pytest.mark.asyncio
    async def test_generate_image_flag_echoed(self, _stub_generation, tool_callable):
        result = await tool_callable(query="rome 50 BCE", generate_image=True, preset="hd")
        assert "error" not in result, result
        assert result["generate_image"] is True
        assert result["preset"] == "hd"

    @pytest.mark.asyncio
    async def test_whitespace_query_is_trimmed(self, _stub_generation, tool_callable):
        result = await tool_callable(query="   rome 50 BCE   ")
        assert "error" not in result, result
        assert result["query"] == "rome 50 BCE"

    @pytest.mark.asyncio
    async def test_empty_strings_for_optional_fields_are_ignored(
        self, _stub_generation, tool_callable
    ):
        """Empty strings for preset/visibility/model_policy should not error."""
        result = await tool_callable(query="rome 50 BCE", preset="", visibility="", model_policy="")
        assert "error" not in result, result


# ============================================================================
# End-to-end: FastAPI app with MCP mounted at /mcp
# ============================================================================


@pytest.mark.fast
class TestFastAPIIntegration:
    """Full-stack checks against the production FastAPI app.

    The MCP streamable HTTP session manager is a module-level singleton whose
    ``.run()`` can only be called once per process, so we build the app and
    client once per class and share them across tests.
    """

    @pytest.fixture(scope="class")
    def client(self):
        from app.main import app

        with TestClient(app) as client:
            yield client

    def test_mcp_requires_bearer(self, client):
        response = client.get("/mcp/")
        assert response.status_code == 401
        body = response.json()
        assert body["error"] == "Unauthorized"
        assert response.headers.get("www-authenticate", "").startswith("Bearer")

    def test_mcp_post_requires_bearer(self, client):
        response = client.post("/mcp/", json={})
        assert response.status_code == 401

    def test_mcp_with_invalid_bearer_rejected(self, client):
        response = client.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Authorization": "Bearer nonsense"},
        )
        assert response.status_code == 401

    def test_health_endpoint_still_works(self, client):
        """Mounting MCP must not break unrelated routes."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] in ("healthy", "degraded")

    def test_mcp_tool_is_registered(self):
        """The tp_flash_generate tool must be registered on the MCP server."""
        from app.mcp_server import mcp

        # FastMCP's tool manager exposes ``_tools`` (older) or a ``tools``
        # accessor (newer).  We try a few access patterns.
        tool_names: list[str] = []
        manager = getattr(mcp, "_tool_manager", None) or getattr(mcp, "tool_manager", None)
        if manager is not None:
            tools = getattr(manager, "_tools", None) or getattr(manager, "tools", None)
            if isinstance(tools, dict):
                tool_names = list(tools.keys())
            elif tools is not None:
                tool_names = [getattr(t, "name", str(t)) for t in tools]

        if not tool_names:
            # Fallback — search the MCP object dict for any tool-like attribute.
            for attr in ("_tools", "tools"):
                obj = getattr(mcp, attr, None)
                if isinstance(obj, dict):
                    tool_names = list(obj.keys())
                    break

        assert "tp_flash_generate" in tool_names, (
            f"Expected tp_flash_generate to be registered. Found: {tool_names}"
        )
