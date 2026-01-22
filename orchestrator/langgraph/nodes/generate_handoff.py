"""Generate handoff node for workflow completion or pause.

Creates a comprehensive handoff brief when the workflow completes or
is interrupted, enabling seamless session resumption.
"""

import logging
from pathlib import Path
from typing import Any

from orchestrator.langgraph.state import WorkflowState
from orchestrator.utils.handoff import HandoffGenerator, generate_handoff

logger = logging.getLogger(__name__)


async def generate_handoff_node(state: WorkflowState) -> dict[str, Any]:
    """Generate handoff brief for session completion or pause.

    This node runs at workflow completion or when interrupting to
    create a comprehensive brief for resumption.

    Args:
        state: Current workflow state

    Returns:
        Updated state with handoff file path
    """
    logger.info("Generating handoff brief for session")

    project_dir = state.get("project_dir")
    if not project_dir:
        logger.error("No project_dir in state, cannot generate handoff")
        return {"last_handoff": None}

    project_path = Path(project_dir)

    try:
        # Generate the handoff brief
        generator = HandoffGenerator(project_path)
        brief = generator.generate()

        # Save to files
        json_path, md_path = generator.save(brief)

        logger.info(f"Handoff brief generated: {md_path}")

        # Log key stats for visibility
        logger.info(
            f"Handoff summary: Phase {brief.current_phase}, "
            f"{len(brief.completed_tasks)}/{brief.total_tasks} tasks, "
            f"Next: {brief.next_action[:60]}..."
        )

        # Return the markdown path for easy reference
        return {
            "last_handoff": str(md_path),
        }

    except Exception as e:
        logger.error(f"Failed to generate handoff brief: {e}")
        return {"last_handoff": None}


def generate_handoff_sync(project_dir: Path) -> str:
    """Synchronous wrapper for handoff generation.

    Used when generating handoff outside the async workflow context.

    Args:
        project_dir: Project directory

    Returns:
        Path to generated markdown file
    """
    brief = generate_handoff(project_dir, save=True)
    return str(project_dir / ".workflow" / "handoff_brief.md")
