"""Input validators for Pydantic models and dependencies."""

import re
from typing import Annotated, Any

from pydantic import AfterValidator

from ..constants import PROJECT_NAME_PATTERN, WorkflowPhase


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, message: str, field: str = "input"):
        self.message = message
        self.field = field
        super().__init__(message)


def validate_project_name(value: str) -> str:
    """Validate a project name.

    Args:
        value: Project name to validate

    Returns:
        Validated project name

    Raises:
        ValueError: If validation fails
    """
    if not value:
        raise ValueError("Project name cannot be empty")

    if len(value) > 64:
        raise ValueError("Project name cannot exceed 64 characters")

    if not re.match(PROJECT_NAME_PATTERN, value):
        raise ValueError(
            "Project name must start with a letter and contain only "
            "letters, numbers, hyphens, and underscores"
        )

    # Check for reserved names
    reserved = {"api", "admin", "system", "root", "null", "undefined"}
    if value.lower() in reserved:
        raise ValueError(f"Project name '{value}' is reserved")

    return value


def validate_positive_float(value: Any) -> float:
    """Validate a positive float value.

    Args:
        value: Value to validate

    Returns:
        Validated float

    Raises:
        ValueError: If validation fails
    """
    if value is None:
        raise ValueError("Value cannot be None")

    try:
        float_value = float(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Value must be a valid number: {e}")

    if float_value < 0:
        raise ValueError("Value must be positive")

    if float_value > 1_000_000:
        raise ValueError("Value exceeds maximum allowed (1,000,000)")

    return float_value


def validate_phase_number(value: Any) -> int:
    """Validate a workflow phase number.

    Args:
        value: Phase number to validate

    Returns:
        Validated phase number

    Raises:
        ValueError: If validation fails
    """
    if value is None:
        raise ValueError("Phase number cannot be None")

    try:
        int_value = int(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Phase must be a valid integer: {e}")

    valid_phases = {phase.value for phase in WorkflowPhase}
    if int_value not in valid_phases:
        raise ValueError(f"Phase must be one of: {sorted(valid_phases)}")

    return int_value


def validate_budget(value: Any) -> float:
    """Validate a budget value (positive float with reasonable limits).

    Args:
        value: Budget value to validate

    Returns:
        Validated budget

    Raises:
        ValueError: If validation fails
    """
    float_value = validate_positive_float(value)

    # Budget-specific limits
    if float_value > 10_000:
        raise ValueError("Budget cannot exceed $10,000")

    return float_value


# Annotated types for use in Pydantic models
ProjectName = Annotated[str, AfterValidator(validate_project_name)]
PositiveFloat = Annotated[float, AfterValidator(validate_positive_float)]
PhaseNumber = Annotated[int, AfterValidator(validate_phase_number)]
BudgetValue = Annotated[float, AfterValidator(validate_budget)]
