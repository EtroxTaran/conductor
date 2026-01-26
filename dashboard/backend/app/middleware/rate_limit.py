"""Rate limiting middleware using sliding window algorithm."""

import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_minute: int = 60
    requests_per_second: int = 10
    enabled: bool = True
    # Paths with custom limits (path -> (per_minute, per_second))
    path_overrides: dict[str, tuple[int, int]] = field(default_factory=dict)
    # Paths to skip rate limiting
    skip_paths: set[str] = field(default_factory=set)


@dataclass
class ClientState:
    """Tracks request timestamps for a client."""

    timestamps: list[float] = field(default_factory=list)
    lock: Lock = field(default_factory=Lock)

    def cleanup(self, window_seconds: float) -> None:
        """Remove timestamps outside the window."""
        cutoff = time.time() - window_seconds
        self.timestamps = [ts for ts in self.timestamps if ts > cutoff]

    def count_in_window(self, window_seconds: float) -> int:
        """Count requests in the specified time window."""
        cutoff = time.time() - window_seconds
        return sum(1 for ts in self.timestamps if ts > cutoff)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limiting middleware.

    Limits requests per client IP using a sliding window algorithm.
    Supports both per-second and per-minute limits.
    """

    def __init__(
        self,
        app: ASGIApp,
        config: Optional[RateLimitConfig] = None,
    ):
        """Initialize the rate limiter.

        Args:
            app: ASGI application
            config: Rate limit configuration
        """
        super().__init__(app)
        self.config = config or RateLimitConfig()
        self._clients: dict[str, ClientState] = defaultdict(ClientState)
        self._global_lock = Lock()

        # Default skip paths
        self.config.skip_paths.update({"/health", "/", "/docs", "/redoc", "/openapi.json"})

        # Default path overrides - chat endpoints get lower limits
        if not self.config.path_overrides:
            self.config.path_overrides = {
                "/api/chat": (10, 2),  # 10/min, 2/sec
                "/api/chat/command": (10, 2),
            }

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        """Check rate limits and process request."""
        if not self.config.enabled:
            return await call_next(request)

        path = request.url.path

        # Skip rate limiting for certain paths
        if path in self.config.skip_paths:
            return await call_next(request)

        # Get client identifier
        client_id = self._get_client_id(request)

        # Get limits for this path
        per_minute, per_second = self._get_limits(path)

        # Check and update rate limits
        allowed, retry_after = self._check_rate_limit(client_id, per_minute, per_second)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Please slow down.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining_minute = max(0, per_minute - self._get_count(client_id, 60))
        response.headers["X-RateLimit-Limit"] = str(per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining_minute)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)

        return response

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request."""
        # Check for forwarded header first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        # Use client IP
        if request.client:
            return request.client.host

        return "unknown"

    def _get_limits(self, path: str) -> tuple[int, int]:
        """Get rate limits for a path."""
        # Check for exact match
        if path in self.config.path_overrides:
            return self.config.path_overrides[path]

        # Check for prefix match
        for pattern, limits in self.config.path_overrides.items():
            if path.startswith(pattern):
                return limits

        # Return default limits
        return (self.config.requests_per_minute, self.config.requests_per_second)

    def _check_rate_limit(
        self,
        client_id: str,
        per_minute: int,
        per_second: int,
    ) -> tuple[bool, int]:
        """Check if request is within rate limits.

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        now = time.time()

        with self._global_lock:
            state = self._clients[client_id]

        with state.lock:
            # Cleanup old timestamps
            state.cleanup(60)

            # Check per-second limit
            count_second = state.count_in_window(1)
            if count_second >= per_second:
                return (False, 1)

            # Check per-minute limit
            count_minute = len(state.timestamps)
            if count_minute >= per_minute:
                # Find when oldest request will expire
                if state.timestamps:
                    oldest = min(state.timestamps)
                    retry_after = int(60 - (now - oldest)) + 1
                    return (False, max(1, retry_after))
                return (False, 60)

            # Record this request
            state.timestamps.append(now)

        return (True, 0)

    def _get_count(self, client_id: str, window_seconds: float) -> int:
        """Get request count for a client in the specified window."""
        with self._global_lock:
            state = self._clients.get(client_id)

        if not state:
            return 0

        with state.lock:
            return state.count_in_window(window_seconds)

    def reset_client(self, client_id: str) -> None:
        """Reset rate limit state for a client (for testing)."""
        with self._global_lock:
            if client_id in self._clients:
                del self._clients[client_id]
