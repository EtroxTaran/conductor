"""Middleware modules for the dashboard API."""

from .rate_limit import RateLimitMiddleware

__all__ = ["RateLimitMiddleware"]
