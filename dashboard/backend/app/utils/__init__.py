"""Utility modules for the dashboard API."""

from .errors import (
    APIError,
    InternalError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    register_exception_handlers,
    safe_json_load,
)
from .logging import RequestLoggingMiddleware

__all__ = [
    # Errors
    "APIError",
    "NotFoundError",
    "ValidationError",
    "InternalError",
    "RateLimitError",
    "safe_json_load",
    "register_exception_handlers",
    # Logging
    "RequestLoggingMiddleware",
]
