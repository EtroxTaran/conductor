"""Configuration package for workflow settings.

Provides configurable thresholds, feature flags, and project-type
specific defaults. Includes JSON schema validation for configuration files.
"""

from .thresholds import (
    DEFAULT_CONFIGS,
    ConfigValidationError,
    ProjectConfig,
    QualityConfig,
    RetryConfig,
    SecurityConfig,
    ValidationConfig,
    WorkflowConfig,
    get_project_config,
    load_project_config,
    validate_config,
)

__all__ = [
    "ProjectConfig",
    "ValidationConfig",
    "QualityConfig",
    "SecurityConfig",
    "WorkflowConfig",
    "RetryConfig",
    "DEFAULT_CONFIGS",
    "get_project_config",
    "load_project_config",
    "validate_config",
    "ConfigValidationError",
]
