# Lessons Learned

<!-- SHARED: This file applies to ALL agents -->
<!-- Add new lessons at the TOP of this file -->
<!-- Version: 1.4 -->
<!-- Last Updated: 2026-01-22 -->

## How to Add a Lesson

When you discover a bug, mistake, or pattern that should be remembered:

1. Add a new entry at the TOP of the "Recent Lessons" section
2. Follow the template format
3. Run `python scripts/sync-rules.py` to propagate

---

## Recent Lessons

### 2026-01-22 - Enhanced CLI Utilization for Quality and Automation

- **Issue**: Claude CLI tools used in basic single-shot manner, missing powerful quality-enhancing features like plan mode, session continuity, schema validation, and audit trails
- **Root Cause**: Enhanced CLI flags (`--permission-mode plan`, `--resume`, `--json-schema`, `--max-budget-usd`) were not utilized by the orchestrator
- **Fix**: Implemented 8 enhancements across 4 phases:
  1. **Plan Mode**: Auto-detect when to use `--permission-mode plan` (files ≥ 3 OR high complexity)
  2. **Session Continuity**: `SessionManager` for `--resume`/`--session-id` across Ralph loop iterations
  3. **Error Context Preservation**: `ErrorContextManager` with auto-classification and suggestions for intelligent retries
  4. **Comprehensive Audit Trail**: Thread-safe JSONL logging of all CLI invocations with timing, costs, and outcomes
  5. **JSON Schema Validation**: `--json-schema` support for structured output enforcement
  6. **Budget Control**: `BudgetManager` with project/task/invocation limits via `--max-budget-usd`
  7. **Fallback Model**: `--fallback-model sonnet` for automatic failover
  8. **Enhanced ClaudeAgent**: Unified interface integrating all features with autonomous decision-making
- **Prevention**:
  - Use plan mode for ≥3 files OR high complexity tasks (automatic)
  - Resume sessions for Ralph iterations 2+ (preserves debugging context)
  - Always record errors and use enhanced retry prompts
  - Set budget limits on all invocations (default $1.00)
  - Use `should_use_plan_mode()` to let agent decide automatically
- **Applies To**: claude
- **Files Changed**:
  - `orchestrator/agents/session_manager.py` (new - 280 lines)
  - `orchestrator/agents/error_context.py` (new - 400 lines)
  - `orchestrator/agents/budget.py` (new - 450 lines)
  - `orchestrator/audit/__init__.py` (new)
  - `orchestrator/audit/trail.py` (new - 350 lines)
  - `orchestrator/agents/claude_agent.py` (major rewrite - 565 lines)
  - `orchestrator/agents/base.py` (modified - audit integration)
  - `orchestrator/agents/__init__.py` (modified - exports)
  - `shared-rules/cli-reference.md` (updated - enhanced flags, decision matrix, autonomous guidelines)
  - `tests/test_session_manager.py` (new - 21 tests)
  - `tests/test_audit_trail.py` (new - 22 tests)
  - `tests/test_error_context.py` (new - 32 tests)
  - `tests/test_budget.py` (new - 25 tests)
  - `tests/test_claude_agent_enhanced.py` (new - 30 tests)

### 2026-01-21 - Enhanced Nested Architecture with Safety Features

- **Issue**: Orchestrator could accidentally write to project code files; no support for external projects or parallel workers
- **Root Cause**: Missing file boundary enforcement; tight coupling between orchestrator and projects; sequential-only worker execution
- **Fix**: Implemented four major enhancements:
  1. **File Boundary Enforcement**: Orchestrator can only write to `.workflow/` and `.project-config.json`. Violations raise `OrchestratorBoundaryError`.
  2. **External Project Mode**: `--project-path` flag allows running workflow on any directory, not just `projects/`.
  3. **Scoped Worker Prompts**: Minimal context prompts focus workers on specific files, preventing context bloat.
  4. **Git Worktree Parallel Workers**: Independent tasks can run in parallel using isolated git worktrees with automatic cleanup.
- **Prevention**:
  - Always use `safe_write_workflow_file()` and `safe_write_project_config()` in orchestrator
  - Use `validate_orchestrator_write()` before any file write
  - Spawn workers for any code changes; orchestrator never writes code
  - Use worktrees only for independent tasks; verify no shared file modifications
- **Applies To**: claude
- **Files Changed**:
  - `orchestrator/utils/boundaries.py` (new)
  - `orchestrator/utils/worktree.py` (new)
  - `orchestrator/project_manager.py` (modified)
  - `orchestrator/orchestrator.py` (modified)
  - `orchestrator/langgraph/nodes/implement_task.py` (modified)
  - `scripts/init.sh` (modified)
  - `tests/test_boundaries.py` (new)
  - `tests/test_worktree.py` (new)
  - `shared-rules/agent-overrides/claude.md` (updated)
  - `shared-rules/cli-reference.md` (updated)
  - `shared-rules/guardrails.md` (updated)

### 2026-01-21 - Simplified Project Workflow

- **Issue**: Complex templating system with multiple project types, version tracking, and sync mechanisms added unnecessary complexity
- **Root Cause**: Over-engineering for hypothetical future needs
- **Fix**: Simplified to minimal workflow:
  - Projects initialized with just Documents/, .workflow/, and .project-config.json
  - User provides context files (CLAUDE.md, GEMINI.md, .cursor/rules) pre-researched for their project
  - No templates, no version tracking, no sync mechanisms
  - Projects are self-contained with their own git repos
- **Prevention**:
  - Start simple, add complexity only when needed
  - Let users bring their own context rather than generating it
  - Focus on workflow orchestration, not project scaffolding
- **Applies To**: all
- **Files Changed**:
  - Removed: project-templates/, VERSION, CHANGELOG.md
  - Removed: create-project.py, sync-project-templates.py, check-updates.py
  - Removed: update_manager.py, __version__.py
  - Simplified: init.sh, orchestrator.py, project_manager.py

### 2026-01-21 - Ralph Wiggum Loop for TDD Implementation

- **Issue**: Single-shot implementation sometimes fails on complex tasks, requiring full restart
- **Root Cause**: Context degradation during long implementations; no iterative retry mechanism
- **Fix**: Implemented Ralph Wiggum loop pattern:
  - Iterative execution until tests pass (fresh context each iteration)
  - Completion signal: `<promise>DONE</promise>`
  - Auto-detection: uses Ralph loop when `test_files` are defined
  - Configurable via `USE_RALPH_LOOP` environment variable
- **Prevention**:
  - Use Ralph loop for TDD tasks where tests already exist
  - Fresh context per iteration avoids token limit issues
  - Tests provide natural backpressure and completion signal
- **Applies To**: claude
- **Files Changed**:
  - `orchestrator/langgraph/integrations/ralph_loop.py` (new)
  - `orchestrator/langgraph/nodes/implement_task.py` (modified)
  - `tests/test_ralph_loop.py` (new)

### 2026-01-21 - Task-Based Incremental Execution

- **Issue**: One-shot implementation risky for larger features; failures mean redo everything
- **Root Cause**: No incremental verification; no progress visibility for stakeholders
- **Fix**: Implemented task-based execution:
  - Break PRODUCT.md into user stories/tasks via `task_breakdown` node
  - Implement task-by-task in a loop with verification after each
  - Task selection respects dependencies and priorities
  - Optional Linear integration for project tracking
- **Prevention**:
  - Always break features into discrete tasks with clear acceptance criteria
  - Verify each task before moving to next
  - Use dependency tracking to ensure correct execution order
- **Applies To**: all
- **Files Changed**:
  - `orchestrator/langgraph/state.py` (Task, Milestone types)
  - `orchestrator/langgraph/nodes/task_breakdown.py` (new)
  - `orchestrator/langgraph/nodes/select_task.py` (new)
  - `orchestrator/langgraph/nodes/implement_task.py` (new)
  - `orchestrator/langgraph/nodes/verify_task.py` (new)
  - `orchestrator/langgraph/routers/task.py` (new)
  - `orchestrator/langgraph/integrations/linear.py` (new)
  - `tests/test_task_nodes.py` (new)
  - `tests/test_linear_integration.py` (new)

### 2026-01-21 - LangGraph Workflow Architecture

- **Issue**: Need for native parallelism, checkpointing, and human-in-the-loop without custom state management
- **Root Cause**: Original subprocess-based orchestration lacked proper parallel execution and resume capabilities
- **Fix**: Implemented LangGraph StateGraph with:
  - Parallel fan-out/fan-in for Cursor + Gemini (read-only)
  - Sequential implementation node (single writer prevents conflicts)
  - `interrupt()` for human escalation when worker needs clarification
  - SqliteSaver for checkpoint/resume
  - State reducers for merging parallel results
- **Prevention**:
  - Always keep file-writing operations sequential
  - Use state reducers (Annotated types) for parallel merge operations
  - Implement clarification flow for ambiguous requirements
- **Applies To**: all
- **Files Changed**:
  - `orchestrator/langgraph/workflow.py`
  - `orchestrator/langgraph/state.py`
  - `orchestrator/langgraph/nodes/*.py`
  - `orchestrator/langgraph/routers/*.py`
  - `tests/test_langgraph.py`

### 2026-01-20 - CLI Flag Corrections

- **Issue**: Agent CLI commands were using wrong flags
- **Root Cause**: Assumed CLI syntax without verifying documentation
- **Fix**: Updated all agent wrappers with correct flags:
  - `cursor-agent`: Use `--print` for non-interactive, prompt is positional
  - `gemini`: Use `--yolo` for auto-approve, no `--output-format` flag
  - `claude`: Use `-p` followed by prompt, `--output-format json` works
- **Prevention**: Always verify CLI tool flags before implementing. Check `--help` or documentation.
- **Applies To**: all
- **Files Changed**:
  - `orchestrator/agents/cursor_agent.py`
  - `orchestrator/agents/gemini_agent.py`
  - `scripts/call-cursor.sh`
  - `scripts/call-gemini.sh`

---

## Lesson Template

```markdown
### YYYY-MM-DD - Brief Title

- **Issue**: What went wrong or was discovered
- **Root Cause**: Why it happened
- **Fix**: How it was fixed
- **Prevention**: Rule or check to prevent recurrence
- **Applies To**: all | claude | cursor | gemini
- **Files Changed**: List of affected files
```

---

## Archived Lessons

<!-- Move lessons here after 30 days or when the list gets too long -->
<!-- Keep for historical reference -->
