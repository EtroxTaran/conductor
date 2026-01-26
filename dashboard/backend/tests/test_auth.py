"""Tests for API key authentication."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth import _constant_time_compare, optional_api_key, verify_api_key
from app.main import app


class TestConstantTimeCompare:
    """Tests for constant-time string comparison."""

    def test_equal_strings(self):
        """Equal strings should return True."""
        assert _constant_time_compare("secret", "secret") is True

    def test_unequal_strings(self):
        """Unequal strings should return False."""
        assert _constant_time_compare("secret", "wrong") is False

    def test_empty_strings(self):
        """Empty strings should be equal."""
        assert _constant_time_compare("", "") is True

    def test_different_lengths(self):
        """Different length strings should return False."""
        assert _constant_time_compare("short", "much longer string") is False


class TestVerifyApiKey:
    """Tests for API key verification."""

    @pytest.mark.asyncio
    async def test_no_api_key_configured_allows_requests(self):
        """When no API key is configured, requests should be allowed."""
        with patch("app.auth.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                api_key=None,
                debug=False,
                skip_auth_in_debug=False,
            )
            mock_request = MagicMock()
            result = await verify_api_key(mock_request, api_key=None)
            assert result == "unconfigured"

    @pytest.mark.asyncio
    async def test_valid_api_key_allowed(self):
        """Valid API key should be allowed."""
        with patch("app.auth.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                api_key="correct-key",
                debug=False,
                skip_auth_in_debug=False,
            )
            mock_request = MagicMock()
            result = await verify_api_key(mock_request, api_key="correct-key")
            assert result == "correct-key"

    @pytest.mark.asyncio
    async def test_invalid_api_key_rejected(self):
        """Invalid API key should be rejected."""
        with patch("app.auth.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                api_key="correct-key",
                debug=False,
                skip_auth_in_debug=False,
            )
            mock_request = MagicMock()
            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(mock_request, api_key="wrong-key")
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_missing_api_key_rejected(self):
        """Missing API key should be rejected when key is configured."""
        with patch("app.auth.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                api_key="correct-key",
                debug=False,
                skip_auth_in_debug=False,
            )
            mock_request = MagicMock()
            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(mock_request, api_key=None)
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_debug_mode_skips_auth(self):
        """Debug mode with skip_auth_in_debug should skip authentication."""
        with patch("app.auth.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                api_key="correct-key",
                debug=True,
                skip_auth_in_debug=True,
            )
            mock_request = MagicMock()
            result = await verify_api_key(mock_request, api_key=None)
            assert result == "debug-mode"


class TestOptionalApiKey:
    """Tests for optional API key verification."""

    @pytest.mark.asyncio
    async def test_no_key_provided_returns_none(self):
        """No API key provided should return None."""
        result = await optional_api_key(api_key=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_key_returns_key(self):
        """Valid API key should return the key."""
        with patch("app.auth.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(api_key="correct-key")
            result = await optional_api_key(api_key="correct-key")
            assert result == "correct-key"

    @pytest.mark.asyncio
    async def test_invalid_key_returns_none(self):
        """Invalid API key should return None."""
        with patch("app.auth.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(api_key="correct-key")
            result = await optional_api_key(api_key="wrong-key")
            assert result is None


class TestApiKeyIntegration:
    """Integration tests for API key authentication."""

    def test_health_endpoint_no_auth_required(self):
        """Health endpoint should not require authentication."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_root_endpoint_no_auth_required(self):
        """Root endpoint should not require authentication."""
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
