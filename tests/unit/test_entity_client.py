"""Tests for entity resolution client.

Covers:
- Successful batch resolve
- Timeout graceful degradation
- HTTP error graceful degradation
- Empty/missing URL handling
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.entity_client import resolve_figures


@pytest.mark.asyncio
async def test_resolve_figures_success():
    """Mock successful batch resolve — returns name→entity_id mapping."""
    mock_response = httpx.Response(
        200,
        json={
            "results": [
                {"figure": {"id": "fig_abc123", "display_name": "Julius Caesar"}, "created": True},
                {"figure": {"id": "fig_def456", "display_name": "Brutus"}, "created": False},
            ]
        },
        request=httpx.Request("POST", "http://test/api/v1/figures/resolve/batch"),
    )

    with (
        patch("app.core.entity_client.settings") as mock_settings,
        patch("httpx.AsyncClient") as MockClient,
    ):
        mock_settings.CLOCKCHAIN_ENTITY_URL = "http://test"
        mock_settings.CLOCKCHAIN_URL = ""
        mock_settings.CLOCKCHAIN_SERVICE_KEY = "test-key"

        client_instance = AsyncMock()
        client_instance.post.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        result = await resolve_figures(["Julius Caesar", "Brutus"])

    assert result == {"Julius Caesar": "fig_abc123", "Brutus": "fig_def456"}
    client_instance.post.assert_called_once()
    call_kwargs = client_instance.post.call_args
    assert call_kwargs[1]["json"] == {
        "names": [
            {"display_name": "Julius Caesar", "entity_type": "person"},
            {"display_name": "Brutus", "entity_type": "person"},
        ]
    }
    assert call_kwargs[1]["headers"]["X-Service-Key"] == "test-key"


@pytest.mark.asyncio
async def test_resolve_figures_timeout():
    """Mock timeout — should return empty dict, not raise."""
    with (
        patch("app.core.entity_client.settings") as mock_settings,
        patch("httpx.AsyncClient") as MockClient,
    ):
        mock_settings.CLOCKCHAIN_ENTITY_URL = "http://test"
        mock_settings.CLOCKCHAIN_URL = ""
        mock_settings.CLOCKCHAIN_SERVICE_KEY = ""

        client_instance = AsyncMock()
        client_instance.post.side_effect = httpx.ReadTimeout("timed out")
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        result = await resolve_figures(["Napoleon"])

    assert result == {}


@pytest.mark.asyncio
async def test_resolve_figures_error():
    """Mock 500 error — should return empty dict, not raise."""
    mock_response = httpx.Response(
        500,
        json={"error": "internal"},
        request=httpx.Request("POST", "http://test/api/v1/figures/resolve/batch"),
    )

    with (
        patch("app.core.entity_client.settings") as mock_settings,
        patch("httpx.AsyncClient") as MockClient,
    ):
        mock_settings.CLOCKCHAIN_ENTITY_URL = "http://test"
        mock_settings.CLOCKCHAIN_URL = ""
        mock_settings.CLOCKCHAIN_SERVICE_KEY = ""

        client_instance = AsyncMock()
        client_instance.post.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        result = await resolve_figures(["Napoleon"])

    assert result == {}


@pytest.mark.asyncio
async def test_resolve_figures_empty_names():
    """Empty names list should return empty dict without making a request."""
    result = await resolve_figures([])
    assert result == {}


@pytest.mark.asyncio
async def test_resolve_figures_no_url():
    """No URL configured should return empty dict without making a request."""
    with patch("app.core.entity_client.settings") as mock_settings:
        mock_settings.CLOCKCHAIN_ENTITY_URL = ""
        mock_settings.CLOCKCHAIN_URL = ""

        result = await resolve_figures(["Napoleon"])

    assert result == {}


@pytest.mark.asyncio
async def test_resolve_figures_falls_back_to_clockchain_url():
    """When CLOCKCHAIN_ENTITY_URL is empty, should use CLOCKCHAIN_URL."""
    mock_response = httpx.Response(
        200,
        json={
            "results": [
                {"figure": {"id": "fig_xyz", "display_name": "Napoleon"}, "created": True}
            ]
        },
        request=httpx.Request("POST", "http://clockchain/api/v1/figures/resolve/batch"),
    )

    with (
        patch("app.core.entity_client.settings") as mock_settings,
        patch("httpx.AsyncClient") as MockClient,
    ):
        mock_settings.CLOCKCHAIN_ENTITY_URL = ""
        mock_settings.CLOCKCHAIN_URL = "http://clockchain"
        mock_settings.CLOCKCHAIN_SERVICE_KEY = ""

        client_instance = AsyncMock()
        client_instance.post.return_value = mock_response
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        result = await resolve_figures(["Napoleon"])

    assert result == {"Napoleon": "fig_xyz"}
    call_args = client_instance.post.call_args
    assert call_args[0][0] == "http://clockchain/api/v1/figures/resolve/batch"
