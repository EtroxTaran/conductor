"""Configurable thresholds for workflow validation and quality gates.

Provides project-type specific defaults and loading from .project-config.json.
Validates configuration against JSON schema when loaded.
"""

import copy
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..validators.security_scanner import Severity

logger = logging.getLogger(__name__)

# Path to JSON schema for validation
_SCHEMA_PATH = Path(__file__).parent / "project-config.schema.json"
_SCHEMA_CACHE: Optional[dict] = None


class ConfigValidationError(Exception):
    """Raised when configuration fails schema validation."""

    def __init__(self, message: str, errors: Optional[list] = None):
        super().__init__(message)
        self.errors = errors or []


def _get_schema() -> dict:
    """Load and cache the JSON schema."""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        if _SCHEMA_PATH.exists():
            _SCHEMA_CACHE = json.loads(_SCHEMA_PATH.read_text())
        else:
            logger.warning(f"Schema file not found: {_SCHEMA_PATH}")
            _SCHEMA_CACHE = {}
    return _SCHEMA_CACHE


def validate_config(config_data: dict, raise_on_error: bool = False) -> tuple[bool, list[str]]:
    """Validate configuration data against JSON schema.

    Args:
        config_data: Configuration dictionary to validate
        raise_on_error: If True, raise ConfigValidationError on failure

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    schema = _get_schema()
    if not schema:
        # No schema available - skip validation
        return True, []

    errors = []

    try:
        # Try to import jsonschema for validation
        import jsonschema
        from jsonschema import ValidationError, validate

        try:
            validate(instance=config_data, schema=schema)
            return True, []
        except ValidationError:
            # Collect all validation errors
            validator = jsonschema.Draft202012Validator(schema)
            for error in validator.iter_errors(config_data):
                path = ".".join(str(p) for p in error.absolute_path) or "<root>"
                errors.append(f"{path}: {error.message}")

    except ImportError:
        # jsonschema not installed - do basic validation
        logger.debug("jsonschema not installed, using basic validation")
        errors = _basic_validate(config_data)

    if errors and raise_on_error:
        raise ConfigValidationError(
            f"Configuration validation failed with {len(errors)} error(s)",
            errors=errors,
        )

    return len(errors) == 0, errors


def _basic_validate(config_data: dict) -> list[str]:
    """Basic validation without jsonschema library.

    Checks for common issues like invalid types.
    """
    errors = []

    # Validate known fields
    validators = {
        "project_type": lambda v: isinstance(v, str),
        "validation.validation_threshold": lambda v: isinstance(v, int | float) and 0 <= v <= 10,
        "validation.verification_threshold": lambda v: isinstance(v, int | float) and 0 <= v <= 10,
        "validation.max_phase_retries": lambda v: isinstance(v, int) and v >= 1,
        "quality.coverage_threshold": lambda v: isinstance(v, int | float) and 0 <= v <= 100,
        "quality.coverage_blocking": lambda v: isinstance(v, bool),
        "security.enabled": lambda v: isinstance(v, bool),
        "workflow.parallel_workers": lambda v: isinstance(v, int) and v >= 1,
        "retry.enabled": lambda v: isinstance(v, bool),
        "retry.max_task_loop_iterations": lambda v: isinstance(v, int) and v >= 10,
    }

    for path, validator in validators.items():
        value = _get_nested(config_data, path)
        if value is not None and not validator(value):
            errors.append(f"{path}: invalid value {value!r}")

    return errors


def _get_nested(data: dict, path: str) -> Optional[any]:
    """Get nested value from dict using dot notation."""
    keys = path.split(".")
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


@dataclass
class ValidationConfig:
    """Configuration for validation thresholds."""

    validation_threshold: float = 6.0  # Phase 2 minimum score
    verification_threshold: float = 7.0  # Phase 4 minimum score
    max_phase_retries: int = 3


@dataclass
class QualityConfig:
    """Configuration for code quality gates."""

    coverage_threshold: float = 70.0
    coverage_blocking: bool = False
    build_required: bool = True
    lint_required: bool = False


@dataclass
class SecurityConfig:
    """Configuration for security scanning."""

    enabled: bool = True
    blocking_severities: list[Severity] = field(
        default_factory=lambda: [Severity.CRITICAL, Severity.HIGH]
    )


@dataclass
class ResearchConfig:
    """Configuration for research phase."""

    # Basic web search is ON by default (free, all CLIs support it)
    web_research_enabled: bool = True
    web_research_timeout: int = 60

    # Basic tools (default) - free, built into Claude Code
    basic_web_tools: list[str] = field(
        default_factory=lambda: [
            "WebSearch",
            "WebFetch",
        ]
    )

    # Deep research tools (optional) - requires Perplexity API
    perplexity_enabled: bool = False
    perplexity_tools: list[str] = field(
        default_factory=lambda: [
            "mcp__perplexity__perplexity_search",
            "mcp__perplexity__perplexity_ask",
            "mcp__perplexity__perplexity_research",
        ]
    )

    # Ref MCP tools for documentation access (optional but recommended)
    ref_enabled: bool = True
    ref_tools: list[str] = field(
        default_factory=lambda: [
            "mcp__Ref__ref_search_documentation",
            "mcp__Ref__ref_read_url",
        ]
    )

    fallback_on_web_failure: bool = True
    ref_fallback_on_failure: bool = True

    @property
    def web_tools(self) -> list[str]:
        """Get all enabled web tools."""
        tools = list(self.basic_web_tools)
        if self.perplexity_enabled:
            tools.extend(self.perplexity_tools)
        return tools

    @property
    def documentation_tools(self) -> list[str]:
        """Get documentation access tools."""
        if self.ref_enabled:
            return list(self.ref_tools)
        # Fallback to basic web tools for docs if ref not available
        return list(self.basic_web_tools)


@dataclass
class RetryConfig:
    """Configuration for retry policies in LangGraph workflow.

    Controls how agent nodes retry on transient failures.
    """

    # Whether retry is enabled at all
    enabled: bool = True

    # Agent retry policy (Cursor, Gemini nodes)
    agent_max_attempts: int = 3
    agent_initial_interval: float = 1.0  # seconds
    agent_backoff_factor: float = 2.0
    agent_jitter: bool = True

    # Implementation retry policy (longer intervals)
    implementation_max_attempts: int = 2
    implementation_initial_interval: float = 5.0  # seconds
    implementation_backoff_factor: float = 2.0
    implementation_jitter: bool = True

    # Circuit breaker - max total retries across all nodes before HITL escalation
    max_total_retries: int = 10

    # Task loop limit - max iterations through select_task before escalation
    # Prevents infinite loops when tasks keep failing and retrying
    max_task_loop_iterations: int = 50

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "agent_max_attempts": self.agent_max_attempts,
            "agent_initial_interval": self.agent_initial_interval,
            "agent_backoff_factor": self.agent_backoff_factor,
            "agent_jitter": self.agent_jitter,
            "implementation_max_attempts": self.implementation_max_attempts,
            "implementation_initial_interval": self.implementation_initial_interval,
            "implementation_backoff_factor": self.implementation_backoff_factor,
            "implementation_jitter": self.implementation_jitter,
            "max_total_retries": self.max_total_retries,
            "max_task_loop_iterations": self.max_task_loop_iterations,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RetryConfig":
        """Create from dictionary."""
        return cls(
            enabled=data.get("enabled", True),
            agent_max_attempts=data.get("agent_max_attempts", 3),
            agent_initial_interval=data.get("agent_initial_interval", 1.0),
            agent_backoff_factor=data.get("agent_backoff_factor", 2.0),
            agent_jitter=data.get("agent_jitter", True),
            implementation_max_attempts=data.get("implementation_max_attempts", 2),
            implementation_initial_interval=data.get("implementation_initial_interval", 5.0),
            implementation_backoff_factor=data.get("implementation_backoff_factor", 2.0),
            implementation_jitter=data.get("implementation_jitter", True),
            max_total_retries=data.get("max_total_retries", 10),
            max_task_loop_iterations=data.get("max_task_loop_iterations", 50),
        )


@dataclass
class ReviewConfig:
    """Configuration for reviewer timeout and fallback behavior.

    Controls how the workflow handles slow or failing review agents.
    """

    # Timeout for individual reviewers (seconds)
    reviewer_timeout_seconds: int = 300  # 5 minutes

    # Whether to allow single-agent approval when one reviewer fails/times out
    allow_single_agent_approval: bool = True

    # Score penalty when only one reviewer provides feedback
    # Final score = single_agent_score - single_agent_score_penalty
    single_agent_score_penalty: float = 1.0

    # Minimum score for single-agent approval (higher than dual-agent)
    single_agent_minimum_score: float = 7.5

    # Maximum retries for a failed reviewer before falling back
    max_reviewer_retries: int = 2

    # Whether to prefer Cursor or Gemini for single-agent fallback
    # "cursor" = prefer Cursor (security-focused)
    # "gemini" = prefer Gemini (architecture-focused)
    # "any" = use whichever succeeds
    single_agent_preference: str = "any"

    # Whether to log reviewer timeouts for monitoring
    log_timeouts: bool = True


@dataclass
class QualityGateConfig:
    """Configuration for A13 Quality Gate checks."""

    enabled: bool = True
    typescript_strict: bool = True
    eslint_required: bool = True
    naming_conventions: bool = True
    code_structure: bool = True
    max_file_lines: int = 500
    max_function_lines: int = 50
    # Score threshold - below this fails the gate
    minimum_score: float = 6.0
    # What severities block the workflow
    blocking_severities: list[str] = field(
        default_factory=lambda: [
            "CRITICAL",
            "HIGH",
        ]
    )


@dataclass
class DependencyConfig:
    """Configuration for A14 Dependency Checker."""

    enabled: bool = True
    check_npm: bool = True
    check_docker: bool = True
    check_frameworks: bool = True
    # Auto-fix patch/minor updates (major requires approval)
    auto_fix_enabled: bool = False
    # What severities block the workflow
    blocking_severities: list[str] = field(
        default_factory=lambda: [
            "critical",
            "high",
        ]
    )
    # Generate dependabot.yml if missing
    generate_dependabot: bool = True
    # Generate renovate.json if missing (alternative to dependabot)
    generate_renovate: bool = False


@dataclass
class WorkflowFeatures:
    """Feature flags for workflow nodes."""

    documentation_discovery: bool = True  # New: replaces product_validation
    product_validation: bool = True  # Deprecated: use documentation_discovery instead
    environment_check: bool = True
    build_verification: bool = True
    coverage_check: bool = True
    security_scan: bool = True
    approval_gates: bool = False  # Human approval gates
    quality_gate: bool = True  # A13 - TypeScript/ESLint/naming checks
    dependency_check: bool = True  # A14 - Outdated packages/Docker security


@dataclass
class WorkflowConfig:
    """Configuration for workflow behavior."""

    features: WorkflowFeatures = field(default_factory=WorkflowFeatures)
    approval_phases: list[int] = field(default_factory=list)  # Phases requiring human approval
    parallel_workers: int = 1
    review_gating: str = "conservative"


@dataclass
class ProjectConfig:
    """Complete project configuration."""

    project_type: str = "base"
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    research: ResearchConfig = field(default_factory=ResearchConfig)
    quality_gate: QualityGateConfig = field(default_factory=QualityGateConfig)
    dependency: DependencyConfig = field(default_factory=DependencyConfig)
    review: ReviewConfig = field(default_factory=ReviewConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "project_type": self.project_type,
            "validation": {
                "validation_threshold": self.validation.validation_threshold,
                "verification_threshold": self.validation.verification_threshold,
                "max_phase_retries": self.validation.max_phase_retries,
            },
            "quality": {
                "coverage_threshold": self.quality.coverage_threshold,
                "coverage_blocking": self.quality.coverage_blocking,
                "build_required": self.quality.build_required,
                "lint_required": self.quality.lint_required,
            },
            "security": {
                "enabled": self.security.enabled,
                "blocking_severities": [s.value for s in self.security.blocking_severities],
            },
            "workflow": {
                "features": {
                    "product_validation": self.workflow.features.product_validation,
                    "environment_check": self.workflow.features.environment_check,
                    "build_verification": self.workflow.features.build_verification,
                    "coverage_check": self.workflow.features.coverage_check,
                    "security_scan": self.workflow.features.security_scan,
                    "approval_gates": self.workflow.features.approval_gates,
                    "quality_gate": self.workflow.features.quality_gate,
                    "dependency_check": self.workflow.features.dependency_check,
                },
                "approval_phases": self.workflow.approval_phases,
                "parallel_workers": self.workflow.parallel_workers,
                "review_gating": self.workflow.review_gating,
            },
            "research": {
                "web_research_enabled": self.research.web_research_enabled,
                "web_research_timeout": self.research.web_research_timeout,
                "basic_web_tools": self.research.basic_web_tools,
                "perplexity_enabled": self.research.perplexity_enabled,
                "perplexity_tools": self.research.perplexity_tools,
                "ref_enabled": self.research.ref_enabled,
                "ref_tools": self.research.ref_tools,
                "fallback_on_web_failure": self.research.fallback_on_web_failure,
                "ref_fallback_on_failure": self.research.ref_fallback_on_failure,
            },
            "quality_gate": {
                "enabled": self.quality_gate.enabled,
                "typescript_strict": self.quality_gate.typescript_strict,
                "eslint_required": self.quality_gate.eslint_required,
                "naming_conventions": self.quality_gate.naming_conventions,
                "code_structure": self.quality_gate.code_structure,
                "max_file_lines": self.quality_gate.max_file_lines,
                "max_function_lines": self.quality_gate.max_function_lines,
                "minimum_score": self.quality_gate.minimum_score,
                "blocking_severities": self.quality_gate.blocking_severities,
            },
            "dependency": {
                "enabled": self.dependency.enabled,
                "check_npm": self.dependency.check_npm,
                "check_docker": self.dependency.check_docker,
                "check_frameworks": self.dependency.check_frameworks,
                "auto_fix_enabled": self.dependency.auto_fix_enabled,
                "blocking_severities": self.dependency.blocking_severities,
                "generate_dependabot": self.dependency.generate_dependabot,
                "generate_renovate": self.dependency.generate_renovate,
            },
            "review": {
                "reviewer_timeout_seconds": self.review.reviewer_timeout_seconds,
                "allow_single_agent_approval": self.review.allow_single_agent_approval,
                "single_agent_score_penalty": self.review.single_agent_score_penalty,
                "single_agent_minimum_score": self.review.single_agent_minimum_score,
                "max_reviewer_retries": self.review.max_reviewer_retries,
                "single_agent_preference": self.review.single_agent_preference,
                "log_timeouts": self.review.log_timeouts,
            },
            "retry": self.retry.to_dict(),
        }


# Project-type specific defaults
DEFAULT_CONFIGS: dict[str, ProjectConfig] = {
    "base": ProjectConfig(
        project_type="base",
        validation=ValidationConfig(
            validation_threshold=6.0,
            verification_threshold=7.0,
        ),
        quality=QualityConfig(
            coverage_threshold=70.0,
            coverage_blocking=False,
        ),
    ),
    "react-tanstack": ProjectConfig(
        project_type="react-tanstack",
        validation=ValidationConfig(
            validation_threshold=6.5,
            verification_threshold=7.5,
        ),
        quality=QualityConfig(
            coverage_threshold=80.0,
            coverage_blocking=False,
        ),
    ),
    "node-api": ProjectConfig(
        project_type="node-api",
        validation=ValidationConfig(
            validation_threshold=7.0,
            verification_threshold=8.0,
        ),
        quality=QualityConfig(
            coverage_threshold=85.0,
            coverage_blocking=True,  # APIs need high coverage
        ),
    ),
    "java-spring": ProjectConfig(
        project_type="java-spring",
        validation=ValidationConfig(
            validation_threshold=7.0,
            verification_threshold=8.0,
        ),
        quality=QualityConfig(
            coverage_threshold=80.0,
            coverage_blocking=True,
        ),
    ),
    "nx-fullstack": ProjectConfig(
        project_type="nx-fullstack",
        validation=ValidationConfig(
            validation_threshold=6.5,
            verification_threshold=7.5,
        ),
        quality=QualityConfig(
            coverage_threshold=75.0,
            coverage_blocking=False,
        ),
    ),
    "python": ProjectConfig(
        project_type="python",
        validation=ValidationConfig(
            validation_threshold=6.5,
            verification_threshold=7.5,
        ),
        quality=QualityConfig(
            coverage_threshold=80.0,
            coverage_blocking=False,
        ),
    ),
}


def get_project_config(project_type: str) -> ProjectConfig:
    """Get configuration for a project type.

    Args:
        project_type: Type of project (e.g., "react-tanstack", "node-api")

    Returns:
        ProjectConfig with type-specific defaults (a fresh copy)
    """
    if project_type in DEFAULT_CONFIGS:
        # Return a deep copy to prevent mutation of shared defaults
        return copy.deepcopy(DEFAULT_CONFIGS[project_type])

    # Return base config for unknown types
    logger.warning(f"Unknown project type '{project_type}', using base defaults")
    config = copy.deepcopy(DEFAULT_CONFIGS["base"])
    config.project_type = project_type
    return config


def load_project_config(project_dir: str | Path) -> ProjectConfig:
    """Load project configuration from .project-config.json.

    Falls back to detecting project type from files if no config exists.

    Args:
        project_dir: Path to the project directory

    Returns:
        ProjectConfig with merged settings
    """
    project_dir = Path(project_dir)
    config_file = project_dir / ".project-config.json"

    # Start with base config
    config = ProjectConfig()

    # Try to detect project type from template.json or package.json
    template_file = project_dir / "template.json"
    package_file = project_dir / "package.json"

    detected_type = "base"

    if template_file.exists():
        try:
            template = json.loads(template_file.read_text())
            detected_type = template.get("name", "base")
        except Exception:
            pass
    elif package_file.exists():
        try:
            pkg = json.loads(package_file.read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

            if "react" in deps:
                if "tanstack" in str(deps).lower():
                    detected_type = "react-tanstack"
                else:
                    detected_type = "react-tanstack"  # Default React to tanstack
            elif "express" in deps or "fastify" in deps or "hono" in deps:
                detected_type = "node-api"
            else:
                detected_type = "base"
        except Exception:
            pass

    # Get defaults for detected type
    config = get_project_config(detected_type)

    # Load custom config if exists
    if config_file.exists():
        try:
            custom = json.loads(config_file.read_text())

            # Validate against schema
            is_valid, errors = validate_config(custom)
            if not is_valid:
                logger.warning(
                    f"Config validation warnings for {config_file}:\n"
                    + "\n".join(f"  - {e}" for e in errors)
                )
                # Continue with merge - validation is advisory, not blocking

            config = _merge_config(config, custom)
            logger.info(f"Loaded custom config from {config_file}")
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in {config_file}: {e}")
        except Exception as e:
            logger.warning(f"Error loading config from {config_file}: {e}")

    return config


def _merge_config(base: ProjectConfig, custom: dict) -> ProjectConfig:
    """Merge custom config into base config.

    Args:
        base: Base ProjectConfig
        custom: Custom config dictionary

    Returns:
        Merged ProjectConfig
    """
    # Update project type
    if "project_type" in custom:
        base.project_type = custom["project_type"]

    # Update validation config
    if "validation" in custom:
        v = custom["validation"]
        if "validation_threshold" in v:
            base.validation.validation_threshold = float(v["validation_threshold"])
        if "verification_threshold" in v:
            base.validation.verification_threshold = float(v["verification_threshold"])
        if "max_phase_retries" in v:
            base.validation.max_phase_retries = int(v["max_phase_retries"])

    # Update quality config
    if "quality" in custom:
        q = custom["quality"]
        if "coverage_threshold" in q:
            base.quality.coverage_threshold = float(q["coverage_threshold"])
        if "coverage_blocking" in q:
            base.quality.coverage_blocking = bool(q["coverage_blocking"])
        if "build_required" in q:
            base.quality.build_required = bool(q["build_required"])
        if "lint_required" in q:
            base.quality.lint_required = bool(q["lint_required"])

    # Update security config
    if "security" in custom:
        s = custom["security"]
        if "enabled" in s:
            base.security.enabled = bool(s["enabled"])
        if "blocking_severities" in s:
            base.security.blocking_severities = [
                Severity(sev)
                for sev in s["blocking_severities"]
                if sev in [e.value for e in Severity]
            ]

    # Update workflow config
    if "workflow" in custom:
        w = custom["workflow"]
        if "features" in w:
            f = w["features"]
            if "documentation_discovery" in f:
                base.workflow.features.documentation_discovery = bool(f["documentation_discovery"])
            if "product_validation" in f:
                base.workflow.features.product_validation = bool(f["product_validation"])
            if "environment_check" in f:
                base.workflow.features.environment_check = bool(f["environment_check"])
            if "build_verification" in f:
                base.workflow.features.build_verification = bool(f["build_verification"])
            if "coverage_check" in f:
                base.workflow.features.coverage_check = bool(f["coverage_check"])
            if "security_scan" in f:
                base.workflow.features.security_scan = bool(f["security_scan"])
            if "approval_gates" in f:
                base.workflow.features.approval_gates = bool(f["approval_gates"])
        if "approval_phases" in w:
            base.workflow.approval_phases = list(w["approval_phases"])
        if "parallel_workers" in w:
            base.workflow.parallel_workers = max(1, int(w["parallel_workers"]))
        if "review_gating" in w:
            base.workflow.review_gating = str(w["review_gating"])

    # Update research config
    if "research" in custom:
        r = custom["research"]
        if "web_research_enabled" in r:
            base.research.web_research_enabled = bool(r["web_research_enabled"])
        if "web_research_timeout" in r:
            base.research.web_research_timeout = int(r["web_research_timeout"])
        if "basic_web_tools" in r:
            base.research.basic_web_tools = list(r["basic_web_tools"])
        if "perplexity_enabled" in r:
            base.research.perplexity_enabled = bool(r["perplexity_enabled"])
        if "perplexity_tools" in r:
            base.research.perplexity_tools = list(r["perplexity_tools"])
        if "ref_enabled" in r:
            base.research.ref_enabled = bool(r["ref_enabled"])
        if "ref_tools" in r:
            base.research.ref_tools = list(r["ref_tools"])
        if "fallback_on_web_failure" in r:
            base.research.fallback_on_web_failure = bool(r["fallback_on_web_failure"])
        if "ref_fallback_on_failure" in r:
            base.research.ref_fallback_on_failure = bool(r["ref_fallback_on_failure"])

    # Update quality gate config
    if "quality_gate" in custom:
        qg = custom["quality_gate"]
        if "enabled" in qg:
            base.quality_gate.enabled = bool(qg["enabled"])
        if "typescript_strict" in qg:
            base.quality_gate.typescript_strict = bool(qg["typescript_strict"])
        if "eslint_required" in qg:
            base.quality_gate.eslint_required = bool(qg["eslint_required"])
        if "naming_conventions" in qg:
            base.quality_gate.naming_conventions = bool(qg["naming_conventions"])
        if "code_structure" in qg:
            base.quality_gate.code_structure = bool(qg["code_structure"])
        if "max_file_lines" in qg:
            base.quality_gate.max_file_lines = int(qg["max_file_lines"])
        if "max_function_lines" in qg:
            base.quality_gate.max_function_lines = int(qg["max_function_lines"])
        if "minimum_score" in qg:
            base.quality_gate.minimum_score = float(qg["minimum_score"])
        if "blocking_severities" in qg:
            base.quality_gate.blocking_severities = list(qg["blocking_severities"])

    # Update dependency config
    if "dependency" in custom:
        d = custom["dependency"]
        if "enabled" in d:
            base.dependency.enabled = bool(d["enabled"])
        if "check_npm" in d:
            base.dependency.check_npm = bool(d["check_npm"])
        if "check_docker" in d:
            base.dependency.check_docker = bool(d["check_docker"])
        if "check_frameworks" in d:
            base.dependency.check_frameworks = bool(d["check_frameworks"])
        if "auto_fix_enabled" in d:
            base.dependency.auto_fix_enabled = bool(d["auto_fix_enabled"])
        if "blocking_severities" in d:
            base.dependency.blocking_severities = list(d["blocking_severities"])
        if "generate_dependabot" in d:
            base.dependency.generate_dependabot = bool(d["generate_dependabot"])
        if "generate_renovate" in d:
            base.dependency.generate_renovate = bool(d["generate_renovate"])

    # Handle workflow features for new flags
    if "workflow" in custom and "features" in custom["workflow"]:
        f = custom["workflow"]["features"]
        if "quality_gate" in f:
            base.workflow.features.quality_gate = bool(f["quality_gate"])
        if "dependency_check" in f:
            base.workflow.features.dependency_check = bool(f["dependency_check"])

    # Update review config
    if "review" in custom:
        r = custom["review"]
        if "reviewer_timeout_seconds" in r:
            base.review.reviewer_timeout_seconds = int(r["reviewer_timeout_seconds"])
        if "allow_single_agent_approval" in r:
            base.review.allow_single_agent_approval = bool(r["allow_single_agent_approval"])
        if "single_agent_score_penalty" in r:
            base.review.single_agent_score_penalty = float(r["single_agent_score_penalty"])
        if "single_agent_minimum_score" in r:
            base.review.single_agent_minimum_score = float(r["single_agent_minimum_score"])
        if "max_reviewer_retries" in r:
            base.review.max_reviewer_retries = int(r["max_reviewer_retries"])
        if "single_agent_preference" in r:
            base.review.single_agent_preference = str(r["single_agent_preference"])
        if "log_timeouts" in r:
            base.review.log_timeouts = bool(r["log_timeouts"])

    return base


def save_project_config(project_dir: str | Path, config: ProjectConfig) -> None:
    """Save project configuration to .project-config.json.

    Args:
        project_dir: Path to the project directory
        config: ProjectConfig to save
    """
    project_dir = Path(project_dir)
    config_file = project_dir / ".project-config.json"

    config_dict = config.to_dict()

    config_file.write_text(json.dumps(config_dict, indent=2))
    logger.info(f"Saved config to {config_file}")
