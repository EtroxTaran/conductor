"""Tests for error handling utilities."""

from pathlib import Path
from unittest.mock import MagicMock

from app.utils.errors import (
    APIError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    register_exception_handlers,
    safe_json_load,
)


class TestAPIError:
    """Tests for base APIError."""

    def test_default_values(self):
        """Should have default values."""
        error = APIError()
        assert error.status_code == 500
        assert error.error_code == "INTERNAL_ERROR"
        assert error.message == "An internal error occurred"
        assert error.detail is None

    def test_custom_message(self):
        """Should accept custom message."""
        error = APIError(message="Custom error")
        assert error.message == "Custom error"

    def test_custom_error_code(self):
        """Should accept custom error code."""
        error = APIError(error_code="CUSTOM_ERROR")
        assert error.error_code == "CUSTOM_ERROR"

    def test_with_detail(self):
        """Should include detail if provided."""
        error = APIError(detail="More info")
        assert error.detail == "More info"

    def test_to_dict(self):
        """Should convert to dictionary."""
        error = APIError(message="Test", detail="Details")
        result = error.to_dict()

        assert result["error"] == "INTERNAL_ERROR"
        assert result["message"] == "Test"
        assert result["status_code"] == 500
        assert result["detail"] == "Details"


class TestNotFoundError:
    """Tests for NotFoundError."""

    def test_defaults(self):
        """Should have 404 defaults."""
        error = NotFoundError()
        assert error.status_code == 404
        assert error.error_code == "NOT_FOUND"

    def test_custom_message(self):
        """Should accept custom message."""
        error = NotFoundError(message="Project not found")
        assert error.message == "Project not found"


class TestValidationError:
    """Tests for ValidationError."""

    def test_defaults(self):
        """Should have 400 defaults."""
        error = ValidationError()
        assert error.status_code == 400
        assert error.error_code == "VALIDATION_ERROR"


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_defaults(self):
        """Should have 429 defaults."""
        error = RateLimitError()
        assert error.status_code == 429
        assert error.error_code == "RATE_LIMIT_EXCEEDED"


class TestSafeJsonLoad:
    """Tests for safe_json_load context manager."""

    def test_valid_json_string(self):
        """Should parse valid JSON string."""
        json_str = '{"key": "value"}'
        with safe_json_load(json_str, context="test") as data:
            assert data == {"key": "value"}

    def test_valid_json_bytes(self):
        """Should parse valid JSON bytes."""
        json_bytes = b'{"key": "value"}'
        with safe_json_load(json_bytes, context="test") as data:
            assert data == {"key": "value"}

    def test_valid_json_file(self, tmp_path: Path):
        """Should parse valid JSON file."""
        file_path = tmp_path / "test.json"
        file_path.write_text('{"key": "value"}')

        with safe_json_load(file_path, context="test") as data:
            assert data == {"key": "value"}

    def test_invalid_json_returns_default(self):
        """Should return default on invalid JSON."""
        invalid_json = "not valid json"
        with safe_json_load(invalid_json, context="test", default={}) as data:
            assert data == {}

    def test_missing_file_returns_default(self, tmp_path: Path):
        """Should return default for missing file."""
        missing_file = tmp_path / "missing.json"
        with safe_json_load(missing_file, context="test", default=None) as data:
            assert data is None

    def test_default_is_none(self):
        """Should default to None if not specified."""
        invalid_json = "not valid"
        with safe_json_load(invalid_json, context="test") as data:
            assert data is None


class TestRegisterExceptionHandlers:
    """Tests for exception handler registration."""

    def test_registers_api_error_handler(self):
        """Should register handler for APIError."""
        app = MagicMock()
        app.add_exception_handler = MagicMock()

        register_exception_handlers(app)

        # Should have called add_exception_handler with APIError
        app.add_exception_handler.assert_called_once()
        call_args = app.add_exception_handler.call_args
        assert call_args[0][0] == APIError
