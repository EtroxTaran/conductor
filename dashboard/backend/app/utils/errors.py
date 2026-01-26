"""Centralized error handling utilities."""

import json
import logging
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional, TypeVar, Union

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

T = TypeVar("T")


class APIError(Exception):
    """Base class for API errors."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An internal error occurred"

    def __init__(
        self,
        message: Optional[str] = None,
        detail: Optional[str] = None,
        error_code: Optional[str] = None,
    ):
        self.message = message or self.message
        self.detail = detail
        if error_code:
            self.error_code = error_code
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for JSON response."""
        result = {
            "error": self.error_code,
            "message": self.message,
            "status_code": self.status_code,
        }
        if self.detail:
            result["detail"] = self.detail
        return result


class NotFoundError(APIError):
    """Resource not found error."""

    status_code = 404
    error_code = "NOT_FOUND"
    message = "Resource not found"


class ValidationError(APIError):
    """Validation error."""

    status_code = 400
    error_code = "VALIDATION_ERROR"
    message = "Validation failed"


class InternalError(APIError):
    """Internal server error."""

    status_code = 500
    error_code = "INTERNAL_ERROR"
    message = "An internal error occurred"


class RateLimitError(APIError):
    """Rate limit exceeded error."""

    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "Rate limit exceeded"


class SanitizationError(APIError):
    """Input sanitization error."""

    status_code = 400
    error_code = "SANITIZATION_ERROR"
    message = "Input contains invalid characters"


@contextmanager
def safe_json_load(
    source: Union[str, Path, bytes],
    context: str = "data",
    default: Optional[T] = None,
) -> Generator[T, None, None]:
    """Safely load JSON with error handling.

    Args:
        source: JSON source (file path, string, or bytes)
        context: Context description for error messages
        default: Default value if parsing fails

    Yields:
        Parsed JSON data or default value

    Example:
        with safe_json_load(file_path, context="session", default={}) as data:
            if not data:
                continue
            process(data)
    """
    try:
        if isinstance(source, Path):
            content = source.read_text()
        elif isinstance(source, bytes):
            content = source.decode("utf-8")
        else:
            content = source

        yield json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse {context} JSON: {e}")
        yield default  # type: ignore
    except OSError as e:
        logger.warning(f"Failed to read {context}: {e}")
        yield default  # type: ignore
    except UnicodeDecodeError as e:
        logger.warning(f"Failed to decode {context}: {e}")
        yield default  # type: ignore


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle APIError exceptions."""
    logger.error(
        f"API error: {exc.error_code} - {exc.message}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error_code": exc.error_code,
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.exception(
        f"Unhandled exception: {type(exc).__name__}",
        extra={
            "path": request.url.path,
            "method": request.method,
        },
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "status_code": 500,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register exception handlers with the FastAPI app.

    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(APIError, api_error_handler)
    # Only catch truly unexpected exceptions
    # FastAPI's default handlers are better for HTTPException, etc.
