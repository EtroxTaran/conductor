"""Product specification validation node.

Validates PRODUCT.md content for completeness and quality
before starting the planning phase.

PRODUCT.md is optional by default. If missing:
1. Try to auto-generate from docs/ folder
2. If auto-generation succeeds, validate the generated file
3. If no PRODUCT.md and not required, continue with docs context
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ...config import load_project_config
from ...validators import ProductValidator
from ..state import WorkflowState
from ..utils.doc_context import load_documentation_context
from ..utils.product_generator import generate_and_save_product_md

logger = logging.getLogger(__name__)


async def product_validation_node(state: WorkflowState) -> dict[str, Any]:
    """Validate PRODUCT.md specification.

    Checks:
    - Required sections are present (if file exists)
    - No placeholder text
    - Minimum content quality

    If PRODUCT.md is missing and auto-generation is enabled,
    attempts to generate one from docs/ folder.

    Args:
        state: Current workflow state

    Returns:
        State updates with validation results
    """
    project_dir = Path(state["project_dir"])
    project_name = state["project_name"]
    logger.info(f"Validating PRODUCT.md for project: {project_name}")

    # Load project config for threshold and feature flags
    config = load_project_config(project_dir)

    # Check if feature is enabled
    if not config.workflow.features.product_validation:
        logger.info("Product validation disabled in config, skipping")
        return {
            "updated_at": datetime.now().isoformat(),
            "next_decision": "continue",
        }

    # Get feature flags
    require_product_md = getattr(config.workflow.features, "require_product_md", False)
    auto_generate = getattr(config.workflow.features, "auto_generate_product_md", True)

    # Find PRODUCT.md file
    product_file = _find_product_file(project_dir)

    # Handle missing PRODUCT.md
    if product_file is None:
        product_file, result = await _handle_missing_product_md(
            project_dir=project_dir,
            project_name=project_name,
            require_product_md=require_product_md,
            auto_generate=auto_generate,
        )

        if result is not None:
            return result

    # Validate the file (either existing or auto-generated)
    return await _validate_product_file(
        project_dir=project_dir,
        project_name=project_name,
        product_file=product_file,
        require_existence=require_product_md,
    )


def _find_product_file(project_dir: Path) -> Optional[Path]:
    """Find PRODUCT.md in standard locations.

    Checks:
    1. project_dir/PRODUCT.md
    2. project_dir/Docs/PRODUCT.md
    3. project_dir/docs/PRODUCT.md

    Args:
        project_dir: Project directory

    Returns:
        Path to PRODUCT.md or None if not found
    """
    locations = [
        project_dir / "PRODUCT.md",
        project_dir / "Docs" / "PRODUCT.md",
        project_dir / "docs" / "PRODUCT.md",
    ]

    for path in locations:
        if path.exists():
            return path

    return None


async def _handle_missing_product_md(
    project_dir: Path,
    project_name: str,
    require_product_md: bool,
    auto_generate: bool,
) -> tuple[Optional[Path], Optional[dict[str, Any]]]:
    """Handle case when PRODUCT.md doesn't exist.

    Args:
        project_dir: Project directory
        project_name: Project name
        require_product_md: Whether PRODUCT.md is required
        auto_generate: Whether to try auto-generation

    Returns:
        Tuple of (product_file_path or None, early_return_result or None)
    """
    logger.info("PRODUCT.md not found, checking options...")

    if auto_generate:
        # Try to auto-generate from docs/
        generated_path = await _try_auto_generate(project_dir, project_name)
        if generated_path:
            logger.info(f"Auto-generated PRODUCT.md at {generated_path}")
            return generated_path, None

    # No auto-generation or it failed
    if require_product_md:
        # PRODUCT.md is required but missing
        return None, _create_missing_error_result()
    else:
        # PRODUCT.md is optional - continue without it
        logger.info("PRODUCT.md is optional and missing, continuing with docs context")
        return None, _create_optional_missing_result(project_name)


async def _try_auto_generate(project_dir: Path, project_name: str) -> Optional[Path]:
    """Try to auto-generate PRODUCT.md from docs/.

    Args:
        project_dir: Project directory
        project_name: Project name

    Returns:
        Path to generated file or None if failed
    """
    try:
        # Load documentation context
        doc_context = load_documentation_context(project_dir, project_name)

        if doc_context.get("source") in ("none", "error"):
            logger.warning("No documentation found for auto-generation")
            return None

        if not doc_context.get("documents"):
            logger.warning("No documents found for auto-generation")
            return None

        # Generate and save
        generated_path = generate_and_save_product_md(project_dir, doc_context)
        return generated_path

    except Exception as e:
        logger.warning(f"Auto-generation failed: {e}")
        return None


def _create_missing_error_result() -> dict[str, Any]:
    """Create error result for missing required PRODUCT.md."""
    return {
        "errors": [
            {
                "type": "missing_product_md",
                "message": (
                    "PRODUCT.md is required but not found.\n\n"
                    "Please create PRODUCT.md in your project root or Docs/ folder.\n"
                    "Alternatively, set 'require_product_md: false' in .project-config.json."
                ),
                "blocking": True,
                "timestamp": datetime.now().isoformat(),
            }
        ],
        "next_decision": "escalate",
        "updated_at": datetime.now().isoformat(),
    }


def _create_optional_missing_result(project_name: str) -> dict[str, Any]:
    """Create result for optional missing PRODUCT.md."""
    from ...db.repositories.phase_outputs import get_phase_output_repository
    from ...storage.async_utils import run_async

    # Save status to database
    validation_result = {
        "timestamp": datetime.now().isoformat(),
        "valid": True,
        "score": 0.0,
        "status": "missing_using_docs_context",
        "message": "PRODUCT.md not found, proceeding with documentation context",
    }

    repo = get_phase_output_repository(project_name)
    run_async(
        repo.save_output(phase=0, output_type="product_validation", content=validation_result)
    )

    return {
        "product_md_status": "missing_using_docs_context",
        "updated_at": datetime.now().isoformat(),
        "next_decision": "continue",
    }


async def _validate_product_file(
    project_dir: Path,
    project_name: str,
    product_file: Optional[Path],
    require_existence: bool,
) -> dict[str, Any]:
    """Validate a PRODUCT.md file.

    Args:
        project_dir: Project directory
        project_name: Project name
        product_file: Path to PRODUCT.md (may be None)
        require_existence: Whether file must exist

    Returns:
        State updates with validation results
    """
    from ...db.repositories.phase_outputs import get_phase_output_repository
    from ...storage.async_utils import run_async

    # If no file and we got here, existence is not required
    if product_file is None:
        return _create_optional_missing_result(project_name)

    # Validate the file
    validator = ProductValidator()
    result = validator.validate_file(product_file, require_existence=require_existence)

    # Save validation results to database
    validation_result = {
        "timestamp": datetime.now().isoformat(),
        "file_path": str(product_file),
        "valid": result.valid,
        "score": result.score,
        "issues": [i.to_dict() for i in result.issues],
        "section_scores": result.section_scores,
        "placeholder_count": result.placeholder_count,
    }

    repo = get_phase_output_repository(project_name)
    run_async(
        repo.save_output(phase=0, output_type="product_validation", content=validation_result)
    )

    if not result.valid:
        logger.warning(
            f"PRODUCT.md validation failed: score={result.score}, issues={len(result.issues)}"
        )

        # Format error message
        error_details = []
        for issue in result.issues:
            error_details.append(f"- [{issue.severity.value}] {issue.section}: {issue.message}")
            if issue.suggestion:
                error_details.append(f"  Suggestion: {issue.suggestion}")

        error_message = (
            f"PRODUCT.md validation failed with score {result.score}/10\n"
            f"Issues found:\n" + "\n".join(error_details)
        )

        return {
            "errors": [
                {
                    "type": "product_validation_failed",
                    "message": error_message,
                    "score": result.score,
                    "issues": [i.to_dict() for i in result.issues],
                    "timestamp": datetime.now().isoformat(),
                }
            ],
            "next_decision": "escalate",
            "updated_at": datetime.now().isoformat(),
        }

    logger.info(f"PRODUCT.md validation passed: score={result.score}")

    return {
        "updated_at": datetime.now().isoformat(),
        "next_decision": "continue",
    }
