"""Tests for rate limiting middleware."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.middleware.rate_limit import ClientState, RateLimitConfig, RateLimitMiddleware


class TestClientState:
    """Tests for ClientState tracking."""

    def test_cleanup_removes_old_timestamps(self):
        """Cleanup should remove timestamps outside the window."""
        state = ClientState()
        now = time.time()

        # Add some old and new timestamps
        state.timestamps = [now - 120, now - 90, now - 30, now - 10, now]

        state.cleanup(60)  # 60 second window

        # Should only keep timestamps within the last 60 seconds
        assert len(state.timestamps) == 3

    def test_count_in_window(self):
        """Should count requests within the specified window."""
        state = ClientState()
        now = time.time()

        state.timestamps = [now - 5, now - 3, now - 1, now]

        assert state.count_in_window(2) == 2  # Last 2 seconds
        assert state.count_in_window(10) == 4  # Last 10 seconds


class TestRateLimitConfig:
    """Tests for RateLimitConfig."""

    def test_default_values(self):
        """Should have sensible defaults."""
        config = RateLimitConfig()
        assert config.requests_per_minute == 60
        assert config.requests_per_second == 10
        assert config.enabled is True

    def test_path_overrides(self):
        """Should support path-specific overrides."""
        config = RateLimitConfig(path_overrides={"/api/chat": (10, 2)})
        assert config.path_overrides["/api/chat"] == (10, 2)


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    @pytest.fixture
    def middleware(self):
        """Create middleware with test config."""
        config = RateLimitConfig(
            requests_per_minute=5,
            requests_per_second=2,
            enabled=True,
        )
        app = MagicMock()
        return RateLimitMiddleware(app, config=config)

    def test_get_limits_default(self, middleware):
        """Should return default limits for unlisted paths."""
        per_min, per_sec = middleware._get_limits("/api/projects")
        assert per_min == 5
        assert per_sec == 2

    def test_get_limits_override(self, middleware):
        """Should return override limits for listed paths."""
        middleware.config.path_overrides["/api/special"] = (1, 1)
        per_min, per_sec = middleware._get_limits("/api/special")
        assert per_min == 1
        assert per_sec == 1

    def test_check_rate_limit_allows_under_limit(self, middleware):
        """Should allow requests under the limit."""
        allowed, retry_after = middleware._check_rate_limit(
            "test-client", per_minute=5, per_second=2
        )
        assert allowed is True
        assert retry_after == 0

    def test_check_rate_limit_blocks_over_per_second(self, middleware):
        """Should block when per-second limit exceeded."""
        client_id = "test-client-1"

        # Make requests up to the per-second limit
        for _ in range(2):
            middleware._check_rate_limit(client_id, per_minute=5, per_second=2)

        # Next request should be blocked
        allowed, retry_after = middleware._check_rate_limit(client_id, per_minute=5, per_second=2)
        assert allowed is False
        assert retry_after == 1

    def test_check_rate_limit_blocks_over_per_minute(self, middleware):
        """Should block when per-minute limit exceeded."""
        client_id = "test-client-2"

        # Make requests up to the per-minute limit (spread out)
        for _ in range(5):
            middleware._check_rate_limit(client_id, per_minute=5, per_second=10)

        # Next request should be blocked
        allowed, retry_after = middleware._check_rate_limit(client_id, per_minute=5, per_second=10)
        assert allowed is False
        assert retry_after > 0

    def test_reset_client(self, middleware):
        """Should reset rate limit state for a client."""
        client_id = "test-client-reset"

        # Make some requests
        middleware._check_rate_limit(client_id, per_minute=5, per_second=2)
        middleware._check_rate_limit(client_id, per_minute=5, per_second=2)

        # Reset
        middleware.reset_client(client_id)

        # Should be able to make requests again
        allowed, _ = middleware._check_rate_limit(client_id, per_minute=5, per_second=2)
        assert allowed is True

    def test_get_client_id_from_direct_client(self, middleware):
        """Should get client ID from direct connection."""
        request = MagicMock()
        request.headers.get.return_value = None
        request.client.host = "192.168.1.1"

        client_id = middleware._get_client_id(request)
        assert client_id == "192.168.1.1"

    def test_get_client_id_from_forwarded_header(self, middleware):
        """Should get client ID from X-Forwarded-For header."""
        request = MagicMock()
        request.headers.get.return_value = "10.0.0.1, 10.0.0.2, 10.0.0.3"

        client_id = middleware._get_client_id(request)
        assert client_id == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_dispatch_skips_health_check(self, middleware):
        """Should skip rate limiting for health check."""
        request = MagicMock()
        request.url.path = "/health"

        call_next = AsyncMock(return_value=MagicMock())

        await middleware.dispatch(request, call_next)

        # Should have called next without rate limiting
        call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_disabled(self, middleware):
        """Should skip rate limiting when disabled."""
        middleware.config.enabled = False
        request = MagicMock()
        request.url.path = "/api/test"

        call_next = AsyncMock(return_value=MagicMock())

        await middleware.dispatch(request, call_next)

        call_next.assert_called_once_with(request)
