"""Model-slug liveness guard (PR-04).

Guards the static ``VerifiedModels`` slug lists + the Find Money quick-sim
``depth`` dial against the ecosystem-wide dead-slug failure mode: a hardcoded
slug that is silently deprecated at the provider 404s → empty/garbled scores
the user paid for (see ``reference_dead_model_slug_failure_mode.md``).

No mocks except the single outbound catalog HTTP GET (the only stubbable
boundary per repo policy). Liveness is a set-membership check against a cached
catalog, so the unit-level tests populate the cache directly — no HTTP, no
LLM tokens.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import ProviderType, VerifiedModels
from app.core.model_registry import OpenRouterModelRegistry

# A realistic Google Gen AI catalog response. Names carry the ``models/``
# prefix exactly as the live API returns them.
SAMPLE_GOOGLE_RESPONSE = {
    "models": [
        {"name": "models/gemini-2.5-flash", "displayName": "Gemini 2.5 Flash"},
        {"name": "models/gemini-2.0-flash", "displayName": "Gemini 2.0 Flash"},
        {"name": "models/gemini-2.5-flash-image", "displayName": "Nano Banana"},
    ]
}

SAMPLE_OPENROUTER_RESPONSE = {
    "data": [
        {"id": "anthropic/claude-opus-4.8", "name": "Claude Opus 4.8"},
        {"id": "google/gemini-2.0-flash-001", "name": "Gemini 2.0 Flash"},
        {"id": "google/gemini-3-flash-preview", "name": "Gemini 3 Flash Preview"},
    ]
}


@pytest.fixture(autouse=True)
def reset_registry():
    OpenRouterModelRegistry.reset()
    yield
    OpenRouterModelRegistry.reset()


def _populate_google(registry: OpenRouterModelRegistry, names: list[str]) -> None:
    """Directly seed the Google catalog cache (no HTTP)."""
    registry._google_models = set(names)


def _populate_openrouter(registry: OpenRouterModelRegistry, ids: list[str]) -> None:
    for i in ids:
        registry._models[i] = {"id": i}


# ---------------------------------------------------------------------------
# Registry-level liveness primitives
# ---------------------------------------------------------------------------
@pytest.mark.fast
class TestRegistryLiveness:
    def test_google_catalog_membership_after_refresh(self):
        """refresh_google strips the models/ prefix and caches bare slugs."""
        registry = OpenRouterModelRegistry.get_instance()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_GOOGLE_RESPONSE

        with patch("app.core.model_registry.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            import asyncio

            ok = asyncio.run(registry.refresh_google(api_key="test-key"))

        assert ok is True
        assert registry.google_model_count == 3
        assert registry.is_google_model_available("gemini-2.5-flash")
        assert not registry.is_google_model_available("models/gemini-2.5-flash")

    def test_refresh_google_no_key_returns_false(self):
        registry = OpenRouterModelRegistry.get_instance()
        import asyncio

        assert asyncio.run(registry.refresh_google(api_key=None)) is False

    def test_refresh_google_non_200_graceful(self):
        registry = OpenRouterModelRegistry.get_instance()
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("app.core.model_registry.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client
            import asyncio

            ok = asyncio.run(registry.refresh_google(api_key="test-key"))
        assert ok is False
        assert registry.google_model_count == 0

    def test_has_catalog(self):
        registry = OpenRouterModelRegistry.get_instance()
        assert not registry.has_catalog(ProviderType.GOOGLE)
        assert not registry.has_catalog(ProviderType.OPENROUTER)
        _populate_google(registry, ["gemini-2.5-flash"])
        _populate_openrouter(registry, ["anthropic/claude-opus-4.8"])
        assert registry.has_catalog(ProviderType.GOOGLE)
        assert registry.has_catalog(ProviderType.OPENROUTER)
        # Stability has no live catalog here.
        assert not registry.has_catalog(ProviderType.STABILITY)

    def test_is_slug_live_google(self):
        registry = OpenRouterModelRegistry.get_instance()
        _populate_google(registry, ["gemini-2.5-flash", "gemini-2.0-flash"])
        assert registry.is_slug_live("gemini-2.5-flash", ProviderType.GOOGLE)
        # A fabricated / deprecated slug is DEAD.
        assert not registry.is_slug_live("gemini-9.9-ultra", ProviderType.GOOGLE)

    def test_is_slug_live_openrouter(self):
        registry = OpenRouterModelRegistry.get_instance()
        _populate_openrouter(registry, ["anthropic/claude-opus-4.8"])
        assert registry.is_slug_live("anthropic/claude-opus-4.8", ProviderType.OPENROUTER)
        assert not registry.is_slug_live("anthropic/claude-3-5-haiku-20241022", ProviderType.OPENROUTER)


# ---------------------------------------------------------------------------
# VerifiedModels.is_slug_live — the config-level classmethod
# ---------------------------------------------------------------------------
@pytest.mark.fast
class TestVerifiedModelsLiveness:
    def test_provider_inference(self):
        assert VerifiedModels.provider_for("gemini-2.5-flash") == ProviderType.GOOGLE
        assert VerifiedModels.provider_for("anthropic/claude-opus-4.8") == ProviderType.OPENROUTER
        assert VerifiedModels.provider_for("stability-ai/sd3.5-large") == ProviderType.STABILITY

    def test_live_slug_passes(self):
        """A slug present in the live catalog passes the liveness check."""
        registry = OpenRouterModelRegistry.get_instance()
        _populate_google(registry, ["gemini-2.5-flash", "gemini-2.0-flash"])
        _populate_openrouter(registry, ["anthropic/claude-opus-4.8"])

        assert VerifiedModels.is_slug_live("gemini-2.5-flash")
        assert VerifiedModels.is_slug_live("anthropic/claude-opus-4.8")

    def test_dead_slug_fails(self):
        """A fabricated slug, with a catalog loaded, is reported DEAD."""
        registry = OpenRouterModelRegistry.get_instance()
        _populate_google(registry, ["gemini-2.5-flash"])

        # Catalog exists for GOOGLE but does not contain this slug → dead.
        assert not VerifiedModels.is_slug_live("gemini-totally-fake", ProviderType.GOOGLE)

    def test_fails_soft_with_no_catalog(self):
        """No catalog loaded → cannot assert death → fail soft (return True)."""
        registry = OpenRouterModelRegistry.get_instance()
        assert registry.google_model_count == 0
        # Even a fabricated slug returns True because absence of a catalog is
        # not evidence the slug is dead.
        assert VerifiedModels.is_slug_live("gemini-totally-fake", ProviderType.GOOGLE)


# ---------------------------------------------------------------------------
# Resolver guard — find_money._resolve_quick_sim_text_model
# ---------------------------------------------------------------------------
@pytest.mark.fast
class TestResolverGuard:
    def test_live_slug_resolves_unchanged(self):
        from app.api.v1.find_money import _resolve_quick_sim_text_model

        registry = OpenRouterModelRegistry.get_instance()
        _populate_google(registry, ["gemini-2.5-flash", "gemini-2.0-flash"])
        _populate_openrouter(registry, ["anthropic/claude-opus-4.8"])

        assert _resolve_quick_sim_text_model(None) == "gemini-2.5-flash"
        assert _resolve_quick_sim_text_model("fast") == "gemini-2.0-flash"
        assert _resolve_quick_sim_text_model("frontier") == "anthropic/claude-opus-4.8"

    def test_dead_nonfrontier_slug_falls_back_loud(self, caplog):
        from app.api.v1.find_money import _QUICK_SIM_TEXT_MODEL, _resolve_quick_sim_text_model

        registry = OpenRouterModelRegistry.get_instance()
        # Catalog has the default but NOT the 'fast' depth slug → fast is dead.
        _populate_google(registry, ["gemini-2.5-flash"])

        import logging

        with caplog.at_level(logging.WARNING):
            resolved = _resolve_quick_sim_text_model("fast")
        assert resolved == _QUICK_SIM_TEXT_MODEL == "gemini-2.5-flash"
        assert any("DEAD" in r.message for r in caplog.records)

    def test_dead_frontier_slug_raises(self):
        from app.api.v1.find_money import (
            DeadFrontierSlugError,
            _resolve_quick_sim_text_model,
        )

        registry = OpenRouterModelRegistry.get_instance()
        # OpenRouter catalog exists but the frontier slug is absent → dead.
        _populate_openrouter(registry, ["google/gemini-2.0-flash-001"])

        with pytest.raises(DeadFrontierSlugError):
            _resolve_quick_sim_text_model("frontier")

    def test_no_catalog_resolves_unchanged(self):
        """With no catalog loaded the resolver fails soft (no regression)."""
        from app.api.v1.find_money import _resolve_quick_sim_text_model

        registry = OpenRouterModelRegistry.get_instance()
        assert registry.google_model_count == 0
        assert registry.model_count == 0
        # All tiers resolve to their configured slug, frontier does NOT raise.
        assert _resolve_quick_sim_text_model(None) == "gemini-2.5-flash"
        assert _resolve_quick_sim_text_model("frontier") == "anthropic/claude-opus-4.8"


# ---------------------------------------------------------------------------
# _simulate_one fails + the batch refunds on a dead frontier slug
# ---------------------------------------------------------------------------
@pytest.mark.fast
class TestSimulateOneFrontierFailure:
    def test_simulate_one_dead_frontier_returns_failure_not_garbage(self):
        import asyncio

        from app.api.v1.find_money import _simulate_one
        from app.schemas.quick_sim import OpportunityIn

        registry = OpenRouterModelRegistry.get_instance()
        # Frontier slug is dead (catalog loaded, slug absent).
        _populate_openrouter(registry, ["google/gemini-2.0-flash-001"])

        result = asyncio.run(
            _simulate_one(
                index=0,
                goal="$50k grant",
                opportunity=OpportunityIn(title="Climate Fund", summary="..."),
                preset=None,
                user_id=None,
                depth="frontier",
            )
        )
        assert result["success"] is False
        assert result["quick_sim"] is None  # never emits a garbage score
        assert result["tdf"] is None
        assert "frontier model unavailable" in result["error"]


# ---------------------------------------------------------------------------
# CI guard — every configured slug must resolve live against a real catalog
# ---------------------------------------------------------------------------
@pytest.mark.fast
class TestEnumerateConfiguredSlugs:
    def test_all_configured_text_slugs_enumerated(self):
        """The enumeration covers GOOGLE_TEXT, OPENROUTER_TEXT, the depth map,
        and the text fallback chain — so the CI guard can't miss a list."""
        slugs = {s for s, _ in VerifiedModels.all_configured_text_slugs()}
        # Spot-check representatives from each source list.
        assert "gemini-2.5-flash" in slugs  # GOOGLE_TEXT
        assert "gemini-2.0-flash" in slugs  # depth map (fast) + GOOGLE_TEXT
        assert "anthropic/claude-opus-4.8" in slugs  # OPENROUTER_TEXT / frontier
        assert "google/gemini-2.0-flash-001" in slugs  # fallback chain

    def test_ci_guard_catches_a_dead_slug(self):
        """Simulate CI: enumerate every slug, assert each is live. A catalog
        missing one of them makes the guard fail loud (the dead-slug failure
        mode becomes a red CI rather than silent prod garbage)."""
        registry = OpenRouterModelRegistry.get_instance()
        all_slugs = VerifiedModels.all_configured_text_slugs()

        google_slugs = [s for s, p in all_slugs if p == ProviderType.GOOGLE]
        or_slugs = [s for s, p in all_slugs if p == ProviderType.OPENROUTER]

        # Seed catalogs with EVERY configured slug EXCEPT one frontier slug.
        _populate_google(registry, google_slugs)
        live_or = [s for s in or_slugs if s != "anthropic/claude-opus-4.8"]
        _populate_openrouter(registry, live_or)

        dead = [s for s, p in all_slugs if not VerifiedModels.is_slug_live(s, p)]
        assert dead == ["anthropic/claude-opus-4.8"]

        # And when the catalog is complete, nothing is dead.
        _populate_openrouter(registry, or_slugs)
        dead_complete = [s for s, p in all_slugs if not VerifiedModels.is_slug_live(s, p)]
        assert dead_complete == []
