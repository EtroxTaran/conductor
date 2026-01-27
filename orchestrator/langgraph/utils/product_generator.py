"""Generate PRODUCT.md from discovered documentation.

Provides utility to auto-generate a PRODUCT.md file from existing
documentation in the docs/ folder when PRODUCT.md is missing.
"""

import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def generate_product_md_from_docs(doc_context: dict[str, Any]) -> Optional[str]:
    """Generate PRODUCT.md content from discovered documentation.

    Creates a minimal but valid PRODUCT.md structure using content
    extracted from the docs/ folder.

    Args:
        doc_context: Documentation context dict from load_documentation_context()
            Expected keys:
            - documents: List of discovered documents
            - product_vision: Product vision text if found
            - acceptance_criteria: List of acceptance criteria
            - architecture_summary: Architecture summary if found
            - content: Combined documentation content

    Returns:
        Generated PRODUCT.md content as string, or None if insufficient docs
    """
    if not doc_context.get("documents"):
        logger.warning("Cannot generate PRODUCT.md - no documents found")
        return None

    parts = [
        "# Feature Specification",
        "",
        "> Auto-generated from project documentation. Review and update as needed.",
        "",
    ]

    # Add summary/product vision
    vision = doc_context.get("product_vision", "")
    if vision:
        parts.extend(
            [
                "## Summary",
                "",
                _truncate(vision, 500),
                "",
            ]
        )
    else:
        # Try to extract from first document
        first_content = _get_first_document_content(doc_context)
        if first_content:
            summary = _extract_summary(first_content)
            parts.extend(
                [
                    "## Summary",
                    "",
                    summary or "[Add a brief summary of the feature]",
                    "",
                ]
            )
        else:
            parts.extend(
                [
                    "## Summary",
                    "",
                    "[Add a brief summary of the feature]",
                    "",
                ]
            )

    # Add problem statement
    parts.extend(
        [
            "## Problem Statement",
            "",
        ]
    )
    problem = _extract_problem_statement(doc_context)
    if problem:
        parts.append(problem)
    else:
        parts.append(
            "This feature addresses requirements documented in the project documentation. "
            "See the docs/ folder for detailed context and background."
        )
    parts.append("")

    # Add acceptance criteria
    parts.extend(
        [
            "## Acceptance Criteria",
            "",
        ]
    )
    criteria = doc_context.get("acceptance_criteria", [])
    if criteria:
        for criterion in criteria[:10]:  # Limit to 10
            parts.append(f"- [ ] {criterion}")
    else:
        parts.append("- [ ] Feature implements documented requirements")
        parts.append("- [ ] All tests pass")
        parts.append("- [ ] Code follows project conventions")
    parts.append("")

    # Add examples section
    parts.extend(
        [
            "## Example Inputs/Outputs",
            "",
            "See project documentation for detailed examples.",
            "",
            "```",
            "// Example placeholder - update with actual examples",
            "```",
            "",
        ]
    )

    # Add technical constraints
    parts.extend(
        [
            "## Technical Constraints",
            "",
        ]
    )
    arch = doc_context.get("architecture_summary", "")
    if arch:
        parts.append(_truncate(arch, 300))
    else:
        parts.append("- Follow existing project architecture and patterns")
        parts.append("- Maintain backward compatibility where applicable")
    parts.append("")

    # Add testing strategy
    parts.extend(
        [
            "## Testing Strategy",
            "",
            "- Unit tests for new functionality",
            "- Integration tests for critical paths",
            "- Manual verification against acceptance criteria",
            "",
        ]
    )

    # Add definition of done
    parts.extend(
        [
            "## Definition of Done",
            "",
            "- [ ] All acceptance criteria met",
            "- [ ] Tests written and passing",
            "- [ ] Code reviewed",
            "- [ ] Documentation updated",
            "- [ ] No critical security issues",
            "",
        ]
    )

    # Add documentation reference
    doc_count = len(doc_context.get("documents", []))
    parts.extend(
        [
            "---",
            "",
            f"*Generated from {doc_count} document(s) in docs/ folder.*",
        ]
    )

    return "\n".join(parts)


def generate_and_save_product_md(
    project_dir: Path,
    doc_context: dict[str, Any],
    target_path: Optional[Path] = None,
) -> Optional[Path]:
    """Generate PRODUCT.md and save to the project.

    Args:
        project_dir: Project directory
        doc_context: Documentation context from load_documentation_context()
        target_path: Where to save (defaults to Docs/PRODUCT.md)

    Returns:
        Path to generated file, or None if generation failed
    """
    content = generate_product_md_from_docs(doc_context)
    if not content:
        return None

    if target_path is None:
        # Default to Docs/PRODUCT.md
        docs_dir = project_dir / "Docs"
        if not docs_dir.exists():
            # Try lowercase docs/
            docs_dir = project_dir / "docs"
        if not docs_dir.exists():
            docs_dir = project_dir / "Docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
        target_path = docs_dir / "PRODUCT.md"

    try:
        target_path.write_text(content, encoding="utf-8")
        logger.info(f"Generated PRODUCT.md at {target_path}")
        return target_path
    except Exception as e:
        logger.error(f"Failed to write generated PRODUCT.md: {e}")
        return None


def _truncate(text: str, max_length: int) -> str:
    """Truncate text to max length, ending at word boundary."""
    if len(text) <= max_length:
        return text
    truncated = text[:max_length].rsplit(" ", 1)[0]
    return truncated.rstrip(".,;:") + "..."


def _get_first_document_content(doc_context: dict[str, Any]) -> Optional[str]:
    """Get content from the first document."""
    documents = doc_context.get("documents", [])
    for doc in documents:
        content = doc.get("content", "")
        if content and len(content) > 50:
            return content
    return None


def _extract_summary(content: str) -> Optional[str]:
    """Extract a summary from document content."""
    import re

    # Look for first paragraph after heading
    match = re.search(r"^#.*?\n\n(.+?)(?:\n\n|\n#)", content, re.MULTILINE | re.DOTALL)
    if match:
        summary = match.group(1).strip()
        return _truncate(summary, 500)

    # Fallback: first 500 chars
    if len(content) > 50:
        return _truncate(content, 500)

    return None


def _extract_problem_statement(doc_context: dict[str, Any]) -> Optional[str]:
    """Extract or derive a problem statement from documentation."""
    import re

    # Check combined content for problem/background sections
    content = doc_context.get("content", "")

    # Look for problem/background section
    patterns = [
        r"##?\s*Problem\s*(?:Statement)?\s*\n+(.+?)(?=\n##|\Z)",
        r"##?\s*Background\s*\n+(.+?)(?=\n##|\Z)",
        r"##?\s*Context\s*\n+(.+?)(?=\n##|\Z)",
        r"##?\s*Motivation\s*\n+(.+?)(?=\n##|\Z)",
    ]

    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            problem = match.group(1).strip()
            if len(problem) >= 50:
                return _truncate(problem, 500)

    return None
