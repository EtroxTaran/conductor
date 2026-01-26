"""API key authentication."""

import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from .config import get_settings

# API key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks.

    Args:
        a: First string
        b: Second string

    Returns:
        True if strings are equal
    """
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


async def verify_api_key(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),
) -> str:
    """Verify the API key from request header.

    Args:
        request: The incoming request
        api_key: API key from X-API-Key header

    Returns:
        The validated API key

    Raises:
        HTTPException: If API key is missing or invalid
    """
    settings = get_settings()

    # Skip authentication in debug mode if configured
    if settings.debug and settings.skip_auth_in_debug:
        return "debug-mode"

    # Check if API key is configured
    if not settings.api_key:
        # No API key configured - allow all requests but log warning
        import logging

        logging.getLogger(__name__).warning("No API key configured - API is unprotected")
        return "unconfigured"

    # Require API key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing API key. Provide X-API-Key header.",
        )

    # Validate API key using constant-time comparison
    if not _constant_time_compare(api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return api_key


async def optional_api_key(
    api_key: Optional[str] = Depends(api_key_header),
) -> Optional[str]:
    """Optionally verify API key (for mixed auth endpoints).

    Args:
        api_key: API key from X-API-Key header

    Returns:
        The API key if provided and valid, None otherwise
    """
    settings = get_settings()

    if not api_key:
        return None

    if not settings.api_key:
        return api_key  # No configured key to validate against

    if _constant_time_compare(api_key, settings.api_key):
        return api_key

    return None
