# CLI Reference (All Agents)

<!-- SHARED: This file applies to ALL agents -->
<!-- Version: 2.0 -->
<!-- Last Updated: 2026-01-21 -->

## Correct CLI Usage

This is the authoritative reference for CLI tool invocation. Always use these patterns.

---

## Claude Code CLI

**Command**: `claude`

### Non-Interactive Mode
```bash
claude -p "Your prompt here" --output-format json
```

### Key Flags (Basic)
| Flag | Purpose | Example |
|------|---------|---------|
| `-p` | Prompt (non-interactive) | `-p "What is 2+2?"` |
| `--output-format` | Output format | `--output-format json` |
| `--allowedTools` | Restrict tools | `--allowedTools "Read,Write,Edit"` |
| `--max-turns` | Limit turns | `--max-turns 10` |

### Enhanced Flags (Use These!)
| Flag | Purpose | When to Use |
|------|---------|-------------|
| `--permission-mode plan` | Plan before implementing | Tasks touching ≥3 files OR high complexity |
| `--resume <session-id>` | Continue previous session | Ralph loop iterations (preserves debugging context) |
| `--session-id <id>` | Set session ID for tracking | New task sessions |
| `--json-schema <path>` | Enforce output structure | Use `schemas/plan-schema.json` or `schemas/tasks-schema.json` |
| `--max-budget-usd <n>` | Limit API cost | Always set (default: $1.00 per invocation) |
| `--fallback-model <model>` | Failover model | Use `sonnet` (default) or `haiku` |

### Decision Matrix: When to Use Enhanced Features

| Scenario | Plan Mode | Session | Budget | Schema |
|----------|-----------|---------|--------|--------|
| Simple 1-2 file task | ❌ | ❌ | ✅ $0.50 | ❌ |
| Multi-file task (≥3 files) | ✅ | ❌ | ✅ $1.00 | ✅ if structured output |
| High complexity task | ✅ | ❌ | ✅ $2.00 | ✅ |
| Ralph loop iteration 1 | ❌ | New session | ✅ $0.50 | ❌ |
| Ralph loop iteration 2+ | ❌ | ✅ Resume | ✅ $0.50 | ❌ |
| Planning phase | ✅ Always | ❌ | ✅ $1.00 | ✅ plan-schema.json |

### Full Example (Enhanced)
```bash
# Complex multi-file task with all features
claude -p "Implement user authentication" \
    --output-format json \
    --permission-mode plan \
    --max-budget-usd 2.00 \
    --fallback-model sonnet \
    --json-schema schemas/tasks-schema.json \
    --allowedTools "Read,Write,Edit,Bash(npm*),Bash(pytest*)" \
    --max-turns 50

# Ralph loop iteration with session continuity
claude -p "Fix failing tests" \
    --output-format json \
    --resume T1-abc123def456 \
    --max-budget-usd 0.50 \
    --allowedTools "Read,Write,Edit,Bash(pytest*)" \
    --max-turns 15
```

### Basic Example
```bash
claude -p "Analyze this code" \
    --output-format json \
    --allowedTools "Read,Grep,Glob" \
    --max-turns 5
```

---

## Cursor Agent CLI

**Command**: `cursor-agent`

### Non-Interactive Mode
```bash
cursor-agent --print --output-format json "Your prompt here"
```

### Key Flags
| Flag | Purpose | Example |
|------|---------|---------|
| `--print` or `-p` | Non-interactive mode | `--print` |
| `--output-format` | Output format | `--output-format json` |
| `--force` | Skip confirmations | `--force` |

### Prompt Position
**IMPORTANT**: Prompt is a POSITIONAL argument at the END, not a flag value.

### Full Example
```bash
cursor-agent --print \
    --output-format json \
    --force \
    "Review this code for security issues"
```

### Common Mistakes
- `cursor-agent -p "prompt"` - Wrong! `-p` means `--print`, not prompt
- Prompt must be LAST argument

---

## Gemini CLI

**Command**: `gemini`

### Non-Interactive Mode
```bash
gemini --yolo "Your prompt here"
```

### Key Flags
| Flag | Purpose | Example |
|------|---------|---------|
| `--yolo` | Auto-approve tool calls | `--yolo` |
| `--model` | Select model | `--model gemini-2.0-flash` |

### Important Notes
- Gemini does NOT support `--output-format`
- Output must be wrapped in JSON externally if needed
- Prompt is a positional argument

### Full Example
```bash
gemini --model gemini-2.0-flash \
    --yolo \
    "Review architecture of this system"
```

### Common Mistakes
- `gemini --output-format json` - Wrong! Flag doesn't exist
- `gemini -p "prompt"` - Wrong! No `-p` flag

---

## Python Orchestrator

**Command**: `python -m orchestrator`

### Project Management
```bash
# Initialize new project
python -m orchestrator --init-project <name>

# List all projects
python -m orchestrator --list-projects
```

### Workflow Commands (Nested Projects)
```bash
# Start workflow for a nested project
python -m orchestrator --project <name> --start
python -m orchestrator --project <name> --use-langgraph --start

# Resume interrupted workflow
python -m orchestrator --project <name> --resume

# Check status
python -m orchestrator --project <name> --status

# Health check
python -m orchestrator --project <name> --health

# Reset workflow
python -m orchestrator --project <name> --reset

# Rollback to phase
python -m orchestrator --project <name> --rollback 3
```

### Workflow Commands (External Projects)
```bash
# Start workflow for external project
python -m orchestrator --project-path /path/to/project --start
python -m orchestrator --project-path ~/repos/my-app --use-langgraph --start

# Check status
python -m orchestrator --project-path /path/to/project --status
```

### Key Flags
| Flag | Purpose | Example |
|------|---------|---------|
| `--project`, `-p` | Project name (nested) | `--project my-app` |
| `--project-path` | External project path | `--project-path ~/repos/my-app` |
| `--start` | Start workflow | `--start` |
| `--resume` | Resume from checkpoint | `--resume` |
| `--status` | Show workflow status | `--status` |
| `--use-langgraph` | Use LangGraph mode | `--use-langgraph` |
| `--health` | Health check | `--health` |
| `--reset` | Reset workflow | `--reset` |
| `--rollback` | Rollback to phase (1-5) | `--rollback 3` |
| `--list-projects` | List all projects | `--list-projects` |
| `--init-project` | Initialize project | `--init-project my-app` |

---

## Shell Script Wrappers

### init.sh - Main Entry Point

```bash
# Check prerequisites
./scripts/init.sh check

# Initialize new project
./scripts/init.sh init <project-name>

# List all projects
./scripts/init.sh list

# Run workflow (nested project)
./scripts/init.sh run <project-name>

# Run workflow (external project)
./scripts/init.sh run --path /path/to/project

# Run with parallel workers (experimental)
./scripts/init.sh run <project-name> --parallel 3

# Check status
./scripts/init.sh status <project-name>

# Show help
./scripts/init.sh help
```

### init.sh Flags
| Flag | Purpose | Example |
|------|---------|---------|
| `--path` | External project path | `run --path ~/repos/app` |
| `--parallel` | Parallel workers count | `run my-app --parallel 3` |

### call-cursor.sh
```bash
bash scripts/call-cursor.sh <prompt-file> <output-file> [project-dir]
```

### call-gemini.sh
```bash
bash scripts/call-gemini.sh <prompt-file> <output-file> [project-dir]
```

---

## Environment Variables

### Orchestrator
```bash
# Enable LangGraph mode
export ORCHESTRATOR_USE_LANGGRAPH=true

# Enable Ralph Wiggum loop for TDD
export USE_RALPH_LOOP=auto  # auto | true | false

# Set parallel workers
export PARALLEL_WORKERS=3
```

### Agent CLI Overrides
```bash
export CURSOR_MODEL=gpt-4-turbo      # Override Cursor model
export GEMINI_MODEL=gemini-2.0-flash  # Override Gemini model
```

---

## Python Orchestrator Modules (For Claude as Tech Lead)

These modules are available for autonomous decision-making. **Use them directly** without asking for permission.

### Session Manager
```python
from orchestrator.agents import SessionManager

# Automatic session continuity for Ralph loop iterations
manager = SessionManager(project_dir)

# Get resume args for existing session (maintains debugging context)
args = manager.get_resume_args("T1")  # Returns ["--resume", "session-id"] or []

# Create new session when starting a task
session = manager.create_session("T1")

# Close session when task completes
manager.close_session("T1")
```

**Decision Rule**: Always use session continuity for Ralph loop iterations 2+. Fresh sessions for new tasks.

### Error Context Manager
```python
from orchestrator.agents import ErrorContextManager

# Automatically record and learn from failures
manager = ErrorContextManager(project_dir)

# Record error when task fails
context = manager.record_error(
    task_id="T1",
    error_message="AssertionError: expected 5, got 3",
    attempt=1,
    stderr=stderr_output,
)

# Build enhanced retry prompt (includes error history + suggestions)
retry_prompt = manager.build_retry_prompt("T1", original_prompt)

# Clear errors when task succeeds
manager.clear_task_errors("T1")
```

**Decision Rule**: Always record errors. Always use enhanced retry prompts. Clear on success.

### Budget Manager
```python
from orchestrator.agents import BudgetManager

manager = BudgetManager(project_dir)

# Check before spending
if manager.can_spend("T1", 0.50):
    # Proceed with invocation
    pass

# Record actual spend
manager.record_spend("T1", "claude", actual_cost)

# Get budget for --max-budget-usd flag
budget = manager.get_invocation_budget("T1")  # Returns float

# Check remaining
remaining = manager.get_task_remaining("T1")
```

**Decision Rule**: Always pass `--max-budget-usd` to CLI. Default $1.00 per invocation, $0.50 for Ralph iterations.

### Audit Trail
```python
from orchestrator.audit import get_project_audit_trail

trail = get_project_audit_trail(project_dir)

# Record invocations (auto-integrated into BaseAgent.run())
with trail.record("claude", "T1", prompt) as entry:
    result = run_command(...)
    entry.set_result(success=True, exit_code=0, cost_usd=0.05)

# Query for debugging
history = trail.get_task_history("T1")
stats = trail.get_statistics()
```

**Decision Rule**: Audit trail is automatic. Use `query()` and `get_statistics()` for debugging failed tasks.

### ClaudeAgent (Enhanced)
```python
from orchestrator.agents import ClaudeAgent

agent = ClaudeAgent(
    project_dir,
    enable_session_continuity=True,  # Default: True
    default_fallback_model="sonnet",  # Default: sonnet
    default_budget_usd=1.00,          # Optional: per-invocation limit
)

# Auto-detects when to use plan mode
result = agent.run_task(task)  # Uses plan mode if task.files >= 3

# Or explicit control
result = agent.run(
    prompt,
    task_id="T1",
    use_plan_mode=True,
    budget_usd=2.00,
    output_schema="plan-schema.json",
)
```

**Decision Rule**: Let `should_use_plan_mode()` decide automatically. Override only when you have specific reasons.

---

## Autonomous Decision Guidelines

**DO automatically (no permission needed):**
- Use plan mode for ≥3 files or high complexity
- Resume sessions for Ralph iterations 2+
- Record errors and use enhanced retry prompts
- Set budget limits on all invocations
- Use fallback model (sonnet by default)

**DO NOT do without asking:**
- Skip budget limits entirely
- Force plan mode on simple tasks
- Clear error history before task actually succeeds
- Change project-wide budget limits

**When uncertain, prefer:**
- Plan mode over no plan mode (safer for quality)
- Session continuity over fresh context (better debugging)
- Lower budget with fallback over higher budget (cost control)
- Recording errors over ignoring them (learn from failures)

---

## Quick Reference Table

| Tool | Non-Interactive | Prompt | Output Format |
|------|-----------------|--------|---------------|
| `claude` | `-p "prompt"` | Part of `-p` | `--output-format json` |
| `cursor-agent` | `--print` | Positional (end) | `--output-format json` |
| `gemini` | `--yolo` | Positional | N/A (wrap externally) |

---

## Complete Workflow Examples

### Example 1: New Nested Project
```bash
# 1. Initialize
./scripts/init.sh init my-api

# 2. Add files (manually)
# - projects/my-api/Documents/
# - projects/my-api/PRODUCT.md
# - projects/my-api/CLAUDE.md

# 3. Run workflow
./scripts/init.sh run my-api
```

### Example 2: External Project
```bash
# 1. Ensure project has PRODUCT.md
# 2. Run workflow
./scripts/init.sh run --path ~/repos/existing-project

# Or via Python
python -m orchestrator --project-path ~/repos/existing-project --use-langgraph --start
```

### Example 3: Parallel Implementation
```bash
# Run with 3 parallel workers for independent tasks
./scripts/init.sh run my-app --parallel 3
```

### Example 4: Check and Resume
```bash
# Check status
./scripts/init.sh status my-app

# If paused, resume
python -m orchestrator --project my-app --resume
```
