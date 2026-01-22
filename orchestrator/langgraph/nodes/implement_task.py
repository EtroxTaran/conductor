"""Implement task node.

Implements a single task using worker Claude with focused scope.
Only implements the current task's acceptance criteria.

Supports two execution modes:
1. Standard: Single worker invocation with TDD prompt
2. Ralph Wiggum: Iterative loop until tests pass (fresh context each iteration)

Ralph Wiggum mode is recommended when tests already exist (TDD workflow).
"""

import asyncio
import concurrent.futures
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..state import (
    WorkflowState,
    Task,
    TaskStatus,
    get_task_by_id,
)
from ..integrations.ralph_loop import (
    RalphLoopConfig,
    run_ralph_loop,
    detect_test_framework,
)
from ..integrations import (
    create_linear_adapter,
    load_issue_mapping,
    create_markdown_tracker,
)
from ..integrations.board_sync import sync_board
from ...specialists.runner import SpecialistRunner
from ...cleanup import CleanupManager
from ...utils.worktree import WorktreeManager, WorktreeError

logger = logging.getLogger(__name__)

# Configuration
TASK_TIMEOUT = 600  # 10 minutes per task (standard mode)
RALPH_TIMEOUT = 1800  # 30 minutes total for Ralph loop
MAX_CONCURRENT_OPERATIONS = 1  # Single writer

# Environment variable to enable Ralph Wiggum mode
USE_RALPH_LOOP = os.environ.get("USE_RALPH_LOOP", "auto")  # "auto", "true", "false"

# Scoped prompt for minimal context workers - focuses only on task-relevant files
SCOPED_TASK_PROMPT = """## Task
{description}

## Acceptance Criteria
{acceptance_criteria}

## Files to Create
{files_to_create}

## Files to Modify
{files_to_modify}

## Test Files
{test_files}

## Instructions
1. Read only the files listed above
2. Implement using TDD (write/update tests first)
3. Do NOT read orchestration files (.workflow/, plan.json)
4. Follow existing code patterns in the project
5. Signal completion with: <promise>DONE</promise>

## Output
When complete, output a JSON object:
{{
    "task_id": "{task_id}",
    "status": "completed",
    "files_created": [],
    "files_modified": [],
    "tests_written": [],
    "tests_passed": true,
    "implementation_notes": "Brief notes"
}}
"""


async def implement_task_node(state: WorkflowState) -> dict[str, Any]:
    """Implement the current task.

    Spawns a worker Claude to implement the single selected task
    with focused scope and TDD practices.

    Supports two modes:
    - Standard: Single worker invocation (default for simple tasks)
    - Ralph Wiggum: Iterative loop until tests pass (for TDD tasks)

    Set USE_RALPH_LOOP env var to control: "auto", "true", "false"

    Args:
        state: Current workflow state

    Returns:
        State updates with task implementation result
    """
    task_id = state.get("current_task_id")
    if not task_id:
        return {
            "errors": [{
                "type": "implement_task_error",
                "message": "No task selected for implementation",
                "timestamp": datetime.now().isoformat(),
            }],
            "next_decision": "escalate",
        }

    task = get_task_by_id(state, task_id)
    if not task:
        return {
            "errors": [{
                "type": "implement_task_error",
                "message": f"Task {task_id} not found",
                "timestamp": datetime.now().isoformat(),
            }],
            "next_decision": "escalate",
        }

    logger.info(f"Implementing task: {task_id} - {task.get('title', 'Unknown')}")

    project_dir = Path(state["project_dir"])

    # Update task attempt count
    updated_task = dict(task)
    updated_task["attempts"] = updated_task.get("attempts", 0) + 1
    updated_task["status"] = TaskStatus.IN_PROGRESS

    # Update task status in trackers
    _update_task_trackers(project_dir, task_id, TaskStatus.IN_PROGRESS)

    # Decide which execution mode to use
    use_ralph = _should_use_ralph_loop(task, project_dir)

    if use_ralph:
        logger.info(f"Using Ralph Wiggum loop for task {task_id}")
        return await _implement_with_ralph_loop(
            state=state,
            task=task,
            updated_task=updated_task,
            project_dir=project_dir,
        )
    else:
        logger.info(f"Using standard implementation for task {task_id}")
        return await _implement_standard(
            state=state,
            task=task,
            updated_task=updated_task,
            project_dir=project_dir,
        )


async def implement_tasks_parallel_node(state: WorkflowState) -> dict[str, Any]:
    """Implement a batch of tasks in parallel using git worktrees.

    Args:
        state: Current workflow state

    Returns:
        State updates with task implementation results
    """
    task_ids = state.get("current_task_ids", [])
    if not task_ids:
        return {
            "errors": [{
                "type": "implement_task_error",
                "message": "No task batch selected for implementation",
                "timestamp": datetime.now().isoformat(),
            }],
            "next_decision": "escalate",
        }

    project_dir = Path(state["project_dir"])
    tasks = []
    for task_id in task_ids:
        task = get_task_by_id(state, task_id)
        if not task:
            return {
                "errors": [{
                    "type": "implement_task_error",
                    "message": f"Task {task_id} not found",
                    "timestamp": datetime.now().isoformat(),
                }],
                "next_decision": "escalate",
            }
        tasks.append(task)

    # Update task attempt counts and statuses
    updated_tasks = []
    for task in tasks:
        updated = dict(task)
        updated["attempts"] = updated.get("attempts", 0) + 1
        updated["status"] = TaskStatus.IN_PROGRESS
        updated_tasks.append(updated)
        _update_task_trackers(project_dir, updated["id"], TaskStatus.IN_PROGRESS)

    results: list[dict] = []
    errors: list[dict] = []
    failed_task_ids: list[str] = []
    retry_task_ids: list[str] = []
    should_escalate = False

    try:
        with WorktreeManager(project_dir) as wt_manager:
            worktrees = []

            for task in tasks:
                try:
                    worktree = wt_manager.create_worktree(task.get("id", "task"))
                    worktrees.append((worktree, task))
                except WorktreeError as e:
                    logger.error(f"Failed to create worktree for task {task.get('id')}: {e}")
                    errors.append({
                        "type": "worktree_error",
                        "task_id": task.get("id"),
                        "message": str(e),
                        "timestamp": datetime.now().isoformat(),
                    })
                    should_escalate = True

            if should_escalate:
                return {
                    "tasks": updated_tasks,
                    "errors": errors,
                    "next_decision": "escalate",
                    "updated_at": datetime.now().isoformat(),
                }

            # Execute tasks in parallel
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(worktrees)) as executor:
                futures = [
                    loop.run_in_executor(
                        executor,
                        _run_task_in_worktree,
                        worktree,
                        task,
                        state,
                    )
                    for worktree, task in worktrees
                ]

                completed = await asyncio.gather(*futures, return_exceptions=True)

            # Process results and merge sequentially
            for (worktree, task), result in zip(worktrees, completed):
                task_id = task.get("id", "unknown")

                if isinstance(result, Exception):
                    logger.error(f"Task {task_id} failed in worktree: {result}")
                    result = {
                        "success": False,
                        "error": str(result),
                        "output": None,
                    }

                if result.get("success"):
                    try:
                        commit_msg = f"Task: {task.get('title', task_id)}"
                        wt_manager.merge_worktree(worktree, commit_msg)
                    except WorktreeError as e:
                        logger.error(f"Failed to merge worktree for task {task_id}: {e}")
                        result = {
                            "success": False,
                            "error": str(e),
                            "output": result.get("output"),
                        }

                results.append({"task_id": task_id, **result})

    except WorktreeError as e:
        logger.error(f"Parallel implementation failed: {e}")
        return {
            "tasks": updated_tasks,
            "errors": [{
                "type": "worktree_error",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            }],
            "next_decision": "escalate",
            "updated_at": datetime.now().isoformat(),
        }

    # Apply task-level updates based on results
    updated_tasks_map = {t["id"]: t for t in updated_tasks}
    for result in results:
        task_id = result["task_id"]
        task = updated_tasks_map.get(task_id, {"id": task_id})

        if result.get("success"):
            output = _parse_task_output(result.get("output", ""), task_id)

            if output.get("status") == "needs_clarification":
                task["status"] = TaskStatus.BLOCKED
                task["error"] = f"Needs clarification: {output.get('question', 'Unknown')}"
                _save_clarification_request(project_dir, task_id, output)
                errors.append({
                    "type": "task_clarification_needed",
                    "task_id": task_id,
                    "question": output.get("question"),
                    "options": output.get("options", []),
                    "timestamp": datetime.now().isoformat(),
                })
                should_escalate = True
                continue

            _save_task_result(project_dir, task_id, output)
            task["implementation_notes"] = output.get("implementation_notes", "")
        else:
            error_message = result.get("error") or "Task implementation failed"
            task_update = _handle_task_error(task, error_message)

            # Capture updates from error handler
            task = task_update["tasks"][0]
            errors.extend(task_update.get("errors", []))
            failed_task_ids.extend(task_update.get("failed_task_ids", []))

            if task_update.get("next_decision") == "retry":
                retry_task_ids.append(task_id)
            else:
                should_escalate = True

        updated_tasks_map[task_id] = task

    # Sync to Kanban board
    try:
        tasks = state.get("tasks", [])
        updated_task_ids = set(updated_tasks_map.keys())
        updated_tasks_list = [t for t in tasks if t["id"] not in updated_task_ids] + list(updated_tasks_map.values())
        sync_state = dict(state)
        sync_state["tasks"] = updated_tasks_list
        sync_board(sync_state)
    except Exception as e:
        logger.warning(f"Failed to sync board in parallel implement: {e}")

    next_decision = "continue"
    current_task_ids = []
    in_flight_task_ids = []
    current_task_id = None

    if should_escalate:
        next_decision = "escalate"
    elif retry_task_ids:
        next_decision = "retry"
        current_task_ids = retry_task_ids
        in_flight_task_ids = retry_task_ids
        current_task_id = retry_task_ids[0]

    return {
        "tasks": list(updated_tasks_map.values()),
        "failed_task_ids": failed_task_ids,
        "errors": errors,
        "current_task_id": current_task_id,
        "current_task_ids": current_task_ids,
        "in_flight_task_ids": in_flight_task_ids,
        "next_decision": next_decision,
        "updated_at": datetime.now().isoformat(),
    }


def _should_use_ralph_loop(task: Task, project_dir: Path) -> bool:
    """Determine whether to use Ralph Wiggum loop for this task.

    Uses Ralph loop when:
    - USE_RALPH_LOOP=true (always use)
    - USE_RALPH_LOOP=auto AND task has test_files defined

    Args:
        task: Task to implement
        project_dir: Project directory

    Returns:
        True if Ralph loop should be used
    """
    ralph_setting = USE_RALPH_LOOP.lower()

    if ralph_setting == "false":
        return False

    if ralph_setting == "true":
        return True

    # Auto mode: use Ralph if tests are specified
    if ralph_setting == "auto":
        test_files = task.get("test_files", [])
        return len(test_files) > 0

    return False


async def _implement_with_ralph_loop(
    state: WorkflowState,
    task: Task,
    updated_task: dict,
    project_dir: Path,
) -> dict[str, Any]:
    """Implement task using Ralph Wiggum iterative loop.

    Runs Claude in a loop until all tests pass, with fresh context
    each iteration to avoid degradation.

    Args:
        state: Workflow state
        task: Task definition
        updated_task: Task with updated attempt count
        project_dir: Project directory

    Returns:
        State updates
    """
    task_id = task["id"]

    # Configure Ralph loop
    test_command = detect_test_framework(project_dir)
    config = RalphLoopConfig(
        max_iterations=10,
        iteration_timeout=300,  # 5 min per iteration
        test_command=test_command,
        save_iteration_logs=True,
    )

    try:
        result = await asyncio.wait_for(
            run_ralph_loop(
                project_dir=project_dir,
                task_id=task_id,
                title=task.get("title", ""),
                user_story=task.get("user_story", ""),
                acceptance_criteria=task.get("acceptance_criteria", []),
                files_to_create=task.get("files_to_create", []),
                files_to_modify=task.get("files_to_modify", []),
                test_files=task.get("test_files", []),
                config=config,
            ),
            timeout=RALPH_TIMEOUT,
        )

        if result.success:
            # Task completed successfully
            _save_task_result(project_dir, task_id, {
                "status": "completed",
                "implementation_mode": "ralph_wiggum",
                "iterations": result.iterations,
                "total_time_seconds": result.total_time_seconds,
                "completion_reason": result.completion_reason,
                **(result.final_output or {}),
            })

            updated_task["implementation_notes"] = (
                f"Completed via Ralph loop in {result.iterations} iteration(s). "
                f"Reason: {result.completion_reason}"
            )

            logger.info(
                f"Task {task_id} completed via Ralph loop "
                f"in {result.iterations} iterations"
            )

            # Cleanup transient/session artifacts for this task
            try:
                cleanup_manager = CleanupManager(project_dir)
                cleanup_result = cleanup_manager.on_task_done(task_id)
                logger.debug(
                    f"Cleanup for task {task_id}: {cleanup_result.total_deleted} items, "
                    f"{cleanup_result.bytes_freed} bytes freed"
                )
            except Exception as e:
                logger.warning(f"Cleanup failed for task {task_id}: {e}")

            return {
                "tasks": [updated_task],
                "next_decision": "continue",  # Go to verify_task
                "updated_at": datetime.now().isoformat(),
            }
        else:
            # Ralph loop failed
            logger.warning(
                f"Ralph loop failed for task {task_id}: {result.error}"
            )
            return _handle_task_error(
                updated_task,
                f"Ralph loop failed after {result.iterations} iterations: {result.error}",
            )

    except asyncio.TimeoutError:
        logger.error(f"Ralph loop for task {task_id} timed out")
        return _handle_task_error(
            updated_task,
            f"Ralph loop timed out after {RALPH_TIMEOUT // 60} minutes",
        )
    except Exception as e:
        logger.error(f"Ralph loop for task {task_id} failed: {e}")
        return _handle_task_error(updated_task, str(e))


async def _implement_standard(
    state: WorkflowState,
    task: Task,
    updated_task: dict,
    project_dir: Path,
) -> dict[str, Any]:
    """Implement task using standard single-invocation approach via Specialist Runner.

    Args:
        state: Workflow state
        task: Task definition
        updated_task: Task with updated attempt count
        project_dir: Project directory

    Returns:
        State updates
    """
    task_id = task["id"]

    # Build prompt using scoped or full context
    prompt = build_task_prompt(task, state, project_dir)

    try:
        # Use SpecialistRunner to execute A04-implementer
        # Running in thread to avoid blocking event loop
        runner = SpecialistRunner(project_dir)
        
        result = await asyncio.to_thread(
            runner.create_agent("A04-implementer").run,
            prompt
        )

        if not result.success:
            raise Exception(result.error or "Task implementation failed")

        # Parse the raw output string into JSON
        output = _parse_task_output(result.output, task_id)

        # Check if worker needs clarification
        if output.get("status") == "needs_clarification":
            logger.info(f"Task {task_id} needs clarification")
            updated_task["status"] = TaskStatus.BLOCKED
            updated_task["error"] = f"Needs clarification: {output.get('question', 'Unknown')}"

            # Save clarification request
            _save_clarification_request(project_dir, task_id, output)

            return {
                "tasks": [updated_task],
                "errors": [{
                    "type": "task_clarification_needed",
                    "task_id": task_id,
                    "question": output.get("question"),
                    "options": output.get("options", []),
                    "timestamp": datetime.now().isoformat(),
                }],
                "next_decision": "escalate",
                "updated_at": datetime.now().isoformat(),
            }

        # Task implemented - save result
        _save_task_result(project_dir, task_id, output)

        # Update task with implementation notes
        updated_task["implementation_notes"] = output.get("implementation_notes", "")

        logger.info(f"Task {task_id} implementation completed")

        # Cleanup transient/session artifacts for this task
        try:
            cleanup_manager = CleanupManager(project_dir)
            cleanup_result = cleanup_manager.on_task_done(task_id)
            logger.debug(
                f"Cleanup for task {task_id}: {cleanup_result.total_deleted} items, "
                f"{cleanup_result.bytes_freed} bytes freed"
            )
        except Exception as e:
            logger.warning(f"Cleanup failed for task {task_id}: {e}")

        # Sync to Kanban board
        try:
            tasks = state.get("tasks", [])
            updated_tasks_list = [t for t in tasks if t["id"] != task_id] + [updated_task]
            sync_state = dict(state)
            sync_state["tasks"] = updated_tasks_list
            sync_board(sync_state)
        except Exception as e:
            logger.warning(f"Failed to sync board in implement task: {e}")

        return {
            "tasks": [updated_task],
            "next_decision": "continue",  # Will go to verify_task
            "updated_at": datetime.now().isoformat(),
        }

    except asyncio.TimeoutError:
        logger.error(f"Task {task_id} timed out after {TASK_TIMEOUT}s")
        return _handle_task_error(
            updated_task,
            f"Task timed out after {TASK_TIMEOUT // 60} minutes",
        )

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        return _handle_task_error(updated_task, str(e))


def _format_criteria(criteria: list[str]) -> str:
    """Format acceptance criteria as numbered list."""
    if not criteria:
        return "- No specific criteria defined"
    return "\n".join(f"- [ ] {c}" for c in criteria)


def _format_files(files: list[str]) -> str:
    """Format file list."""
    if not files:
        return "- None specified"
    return "\n".join(f"- {f}" for f in files)


def build_scoped_prompt(task: Task) -> str:
    """Build a scoped prompt with only task-relevant context.

    This creates a minimal prompt that focuses the worker on:
    - The specific task description
    - Only the files needed for this task
    - Clear instructions to avoid reading orchestration files

    Args:
        task: Task to implement

    Returns:
        Scoped prompt string
    """
    return SCOPED_TASK_PROMPT.format(
        task_id=task.get("id", "unknown"),
        description=task.get("description", task.get("title", "Unknown task")),
        acceptance_criteria="\n".join(
            f"- {c}" for c in task.get("acceptance_criteria", [])
        ) or "- No specific criteria defined",
        files_to_create="\n".join(
            f"- {f}" for f in task.get("files_to_create", [])
        ) or "- None",
        files_to_modify="\n".join(
            f"- {f}" for f in task.get("files_to_modify", [])
        ) or "- None",
        test_files="\n".join(
            f"- {f}" for f in task.get("test_files", [])
        ) or "- None",
    )


def build_full_prompt(task: Task, state: Optional[WorkflowState] = None) -> str:
    """Build a full prompt when file lists are not specified."""
    completed_context = _build_completed_context(state) if state else ""
    description = task.get("description", task.get("title", "Unknown task"))
    user_story = task.get("user_story", "No user story provided")
    dependencies = task.get("dependencies", [])

    prompt = f"""## Task
{description}

## User Story
{user_story}

## Acceptance Criteria
{_format_criteria(task.get("acceptance_criteria", []))}

## Dependencies
{_format_files(dependencies)}

## Files to Create
{_format_files(task.get("files_to_create", []))}

## Files to Modify
{_format_files(task.get("files_to_modify", []))}

## Test Files
{_format_files(task.get("test_files", []))}
"""

    if completed_context:
        prompt += f"\n{completed_context}\n"

    prompt += f"""
## Instructions
1. Implement using TDD (write/update tests first)
2. Follow existing code patterns in the project
3. Do NOT read orchestration files (.workflow/, plan.json)
4. Signal completion with: <promise>DONE</promise>

## Output
When complete, output a JSON object:
{{
    "task_id": "{task.get("id", "unknown")}",
    "status": "completed",
    "files_created": [],
    "files_modified": [],
    "tests_written": [],
    "tests_passed": true,
    "implementation_notes": "Brief notes"
}}
"""

    return prompt.strip()


def build_task_prompt(
    task: Task,
    state: Optional[WorkflowState],
    project_dir: Path,
) -> str:
    """Build a task prompt, preferring scoped context when files are listed.

    Includes CONTEXT.md preferences when available to guide implementation.
    """
    has_file_scope = bool(
        task.get("files_to_create") or task.get("files_to_modify") or task.get("test_files")
    )

    prompt = build_scoped_prompt(task) if has_file_scope else build_full_prompt(task, state)

    # Include CONTEXT.md preferences (GSD pattern)
    context_preferences = _load_context_preferences(project_dir)
    if context_preferences:
        prompt += f"\n\n## Project Context (from CONTEXT.md)\n{context_preferences}"

    # Include research findings if available
    research_findings = _load_research_findings(project_dir)
    if research_findings:
        prompt += f"\n\n## Research Findings\n{research_findings}"

    diff_context = _build_diff_context(project_dir, task)
    if diff_context:
        prompt += f"\n\n## Diff Context\n```diff\n{diff_context}\n```"

    clarification_answers = _load_task_clarification_answers(project_dir, task.get("id", "unknown"))
    if clarification_answers:
        prompt += f"\n\nCLARIFICATION ANSWERS:\n{json.dumps(clarification_answers, indent=2)}"

    return prompt


def _load_context_preferences(project_dir: Path) -> str:
    """Load developer preferences from CONTEXT.md.

    Args:
        project_dir: Project directory

    Returns:
        Formatted preferences string or empty string
    """
    context_file = project_dir / "CONTEXT.md"
    if not context_file.exists():
        return ""

    try:
        content = context_file.read_text()

        # Extract key sections
        sections_to_include = [
            "## Library Preferences",
            "## Architectural Decisions",
            "## Testing Philosophy",
            "## Code Style",
            "## Error Handling",
        ]

        extracted = []
        for section in sections_to_include:
            if section in content:
                section_start = content.find(section)
                next_section = content.find("##", section_start + len(section))
                if next_section == -1:
                    section_content = content[section_start:]
                else:
                    section_content = content[section_start:next_section]

                # Clean up section content
                section_content = section_content.strip()
                if section_content and "[TBD]" not in section_content:
                    extracted.append(section_content)

        if extracted:
            return "\n\n".join(extracted)

    except Exception as e:
        logger.warning(f"Failed to load CONTEXT.md: {e}")

    return ""


def _load_research_findings(project_dir: Path) -> str:
    """Load research findings from the research phase.

    Args:
        project_dir: Project directory

    Returns:
        Formatted research summary or empty string
    """
    findings_file = project_dir / ".workflow" / "phases" / "research" / "findings.json"
    if not findings_file.exists():
        return ""

    try:
        findings = json.loads(findings_file.read_text())

        parts = []

        # Tech stack
        tech_stack = findings.get("tech_stack")
        if tech_stack:
            languages = tech_stack.get("languages", [])
            frameworks = tech_stack.get("frameworks", [])
            if languages:
                parts.append(f"**Languages**: {', '.join(languages)}")
            if frameworks:
                fw_names = [f.get("name", str(f)) if isinstance(f, dict) else str(f) for f in frameworks]
                parts.append(f"**Frameworks**: {', '.join(fw_names)}")

        # Patterns
        patterns = findings.get("existing_patterns")
        if patterns:
            arch = patterns.get("architecture")
            if arch and arch != "unknown":
                parts.append(f"**Architecture**: {arch}")

            testing = patterns.get("testing", {})
            if testing:
                test_info = testing.get("framework") or testing.get("types")
                if test_info:
                    if isinstance(test_info, list):
                        parts.append(f"**Testing**: {', '.join(test_info)}")
                    else:
                        parts.append(f"**Testing**: {test_info}")

        if parts:
            return "\n".join(parts)

    except Exception as e:
        logger.warning(f"Failed to load research findings: {e}")

    return ""


def _build_completed_context(state: Optional[WorkflowState]) -> str:
    """Build context from completed tasks to help with continuity."""
    if not state:
        return ""

    completed_ids = set(state.get("completed_task_ids", []))
    if not completed_ids:
        return ""

    lines = ["## PREVIOUSLY COMPLETED TASKS"]
    for task in state.get("tasks", []):
        task_id = task.get("id")
        if task_id in completed_ids:
            notes = task.get("implementation_notes", "").strip()
            note_line = f" - {notes}" if notes else ""
            lines.append(f"- {task_id}: {task.get('title', 'Untitled')}{note_line}")

    return "\n".join(lines)


def _build_diff_context(project_dir: Path, task: Task, max_chars: int = 4000) -> str:
    """Build git diff context for task-relevant files."""
    import subprocess

    files = []
    for key in ("files_to_create", "files_to_modify", "test_files"):
        files.extend(task.get(key, []) or [])

    files = [f for f in files if f]
    if not files:
        return ""

    try:
        result = subprocess.run(
            ["git", "diff", "--"] + files,
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return ""

        diff = result.stdout.strip()
        if not diff:
            return ""

        return diff[:max_chars]
    except Exception:
        return ""


def _run_task_in_worktree(
    worktree_path: Path,
    task: Task,
    state: Optional[WorkflowState],
) -> dict[str, Any]:
    """Run a task implementation inside a worktree."""
    runner = SpecialistRunner(worktree_path)
    prompt = build_task_prompt(task, state, worktree_path)
    result = runner.create_agent("A04-implementer").run(prompt)

    return {
        "success": result.success,
        "output": result.output or "",
        "error": result.error,
    }


def _load_task_clarification_answers(project_dir: Path, task_id: str) -> dict:
    """Load clarification answers for a specific task."""
    answers_file = project_dir / ".workflow" / "task_clarifications" / f"{task_id}_answers.json"
    if answers_file.exists():
        try:
            return json.loads(answers_file.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _save_clarification_request(project_dir: Path, task_id: str, request: dict) -> None:
    """Save clarification request for human review."""
    clarification_dir = project_dir / ".workflow" / "task_clarifications"
    clarification_dir.mkdir(parents=True, exist_ok=True)

    request_file = clarification_dir / f"{task_id}_request.json"
    request_data = {
        **request,
        "task_id": task_id,
        "timestamp": datetime.now().isoformat(),
    }
    request_file.write_text(json.dumps(request_data, indent=2))


def _save_task_result(project_dir: Path, task_id: str, result: dict) -> None:
    """Save task implementation result."""
    results_dir = project_dir / ".workflow" / "phases" / "task_implementation"
    results_dir.mkdir(parents=True, exist_ok=True)

    result_file = results_dir / f"{task_id}_result.json"
    result_data = {
        **result,
        "task_id": task_id,
        "timestamp": datetime.now().isoformat(),
    }
    result_file.write_text(json.dumps(result_data, indent=2))


def _handle_task_error(task: Task, error_message: str) -> dict[str, Any]:
    """Handle task implementation error.

    Args:
        task: Task that failed
        error_message: Error message

    Returns:
        State update with error
    """
    task_id = task.get("id", "unknown")
    max_attempts = task.get("max_attempts", 3)
    attempts = task.get("attempts", 1)

    task["error"] = error_message

    if attempts >= max_attempts:
        # Max retries exceeded - mark as failed and escalate
        task["status"] = TaskStatus.FAILED
        return {
            "tasks": [task],
            "failed_task_ids": [task_id],
            "errors": [{
                "type": "task_failed",
                "task_id": task_id,
                "message": f"Task failed after {attempts} attempts: {error_message}",
                "timestamp": datetime.now().isoformat(),
            }],
            "next_decision": "escalate",
            "updated_at": datetime.now().isoformat(),
        }
    else:
        # Can retry
        task["status"] = TaskStatus.PENDING
        return {
            "tasks": [task],
            "errors": [{
                "type": "task_error",
                "task_id": task_id,
                "message": error_message,
                "attempt": attempts,
                "timestamp": datetime.now().isoformat(),
            }],
            "next_decision": "retry",
            "updated_at": datetime.now().isoformat(),
        }


def _parse_task_output(stdout: str, task_id: str) -> dict:
    """Parse worker output, extracting task result JSON."""
    if not stdout:
        return {"task_id": task_id, "status": "unknown", "raw_output": ""}

    try:
        parsed = json.loads(stdout)
        if isinstance(parsed, dict):
            parsed["task_id"] = task_id
            return parsed
    except json.JSONDecodeError:
        pass

    # Try to find JSON block in output
    import re
    json_pattern = rf'\{{\s*"task_id"\s*:\s*"{task_id}"[^}}]*\}}'
    match = re.search(json_pattern, stdout, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Generic JSON extraction
    json_match = re.search(r"\{[\s\S]*\}", stdout)
    if json_match:
        try:
            parsed = json.loads(json_match.group(0))
            if isinstance(parsed, dict):
                parsed["task_id"] = task_id
                return parsed
        except json.JSONDecodeError:
            pass

    return {"task_id": task_id, "status": "unknown", "raw_output": stdout}


def _update_task_trackers(
    project_dir: Path,
    task_id: str,
    status: TaskStatus,
    notes: Optional[str] = None,
) -> None:
    """Update task status in markdown tracker and Linear.

    Args:
        project_dir: Project directory
        task_id: Task ID
        status: New status
        notes: Optional status notes
    """
    try:
        # Update markdown tracker
        markdown_tracker = create_markdown_tracker(project_dir)
        markdown_tracker.update_task_status(task_id, status, notes)
    except Exception as e:
        logger.warning(f"Failed to update markdown tracker for task {task_id}: {e}")

    try:
        # Update Linear (if configured and issue exists)
        linear_adapter = create_linear_adapter(project_dir)
        if linear_adapter.enabled:
            # Load issue mapping to populate cache
            issue_mapping = load_issue_mapping(project_dir)
            linear_adapter._issue_cache.update(issue_mapping)
            linear_adapter.update_issue_status(task_id, status)
    except Exception as e:
        logger.warning(f"Failed to update Linear for task {task_id}: {e}")
