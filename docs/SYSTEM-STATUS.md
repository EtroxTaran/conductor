# Meta-Architect System Status

**Last Updated**: 2026-01-21
**Version**: 3.0
**Test Coverage**: 765 tests passing

---

## System Overview

Meta-Architect is a production-grade multi-agent orchestration system that coordinates specialist AI agents (Claude, Cursor, Gemini) to implement features through a structured 5-phase workflow with TDD, 4-eyes review protocol, and comprehensive error recovery.

---

## Core Components

### 1. Task Management System

| Component | Location | Purpose |
|-----------|----------|---------|
| Task Breakdown | `orchestrator/langgraph/nodes/task_breakdown.py` | Parses PRODUCT.md into discrete tasks |
| Task Selection | `orchestrator/langgraph/nodes/select_task.py` | Selects next available task based on priority & dependencies |
| Task Implementation | `orchestrator/langgraph/nodes/implement_task.py` | Spawns worker Claude for implementation |
| Task Verification | `orchestrator/langgraph/nodes/verify_task.py` | Runs tests, verifies file creation |

**Task Flow**:
```
PRODUCT.md → task_breakdown → select_task → implement_task → verify_task → [loop until done]
```

### 2. Agent Registry

| Agent | Role | Primary CLI | Reviewers |
|-------|------|-------------|-----------|
| A01 | Planner | Claude | A08, A02 |
| A02 | Architect | Gemini | A08, A01 |
| A03 | Test Writer | Claude | A08, A07 |
| A04 | Implementer | Claude | A07, A08 |
| A05 | Bug Fixer | Cursor | A10, A08 |
| A06 | Refactorer | Gemini | A08, A07 |
| A07 | Security Reviewer | Cursor | - |
| A08 | Code Reviewer | Gemini | - |
| A09 | Documentation | Claude | A08, A01 |
| A10 | Integration Tester | Claude | A07, A08 |
| A11 | DevOps | Cursor | A07, A08 |
| A12 | UI Designer | Claude | A08, A07 |

**File**: `orchestrator/registry/agents.py`

### 3. Review System (4-Eyes Protocol)

| Component | Location | Purpose |
|-----------|----------|---------|
| Review Cycle | `orchestrator/review/cycle.py` | Manages iterative review-optimize-review loop |
| Conflict Resolver | `orchestrator/review/resolver.py` | Resolves reviewer disagreements with weighted scoring |

**Review Weights**:
- Security issues: Cursor's assessment preferred (0.8 weight)
- Architecture issues: Gemini's assessment preferred (0.7 weight)

**Review Flow**:
```
Agent Work → Cursor Review || Gemini Review → Fan-In → Decision
    ↑                                                    ↓
    └──────────── Feedback Loop ←───────── Needs Changes
```

### 4. Error Handling & Recovery

| Error Type | Recovery Strategy |
|------------|-------------------|
| TRANSIENT | Exponential backoff with jitter (max 3 retries) |
| AGENT_FAILURE | Try backup CLI, then escalate |
| REVIEW_CONFLICT | Apply weights, escalate if unresolved |
| SPEC_MISMATCH | Always escalate (never auto-modify tests) |
| BLOCKING_SECURITY | Immediate halt and escalate |
| TIMEOUT | One retry with extended timeout |

**File**: `orchestrator/recovery/handlers.py`

### 5. Logging System

| Output | Location | Format |
|--------|----------|--------|
| Console | stdout | Colored, human-readable |
| Plain Text | `.workflow/coordination.log` | Timestamped |
| JSON Lines | `.workflow/coordination.jsonl` | Machine-parseable |

**Features**:
- Automatic secrets redaction (API keys, passwords, tokens)
- Thread-safe with locks
- Color-coded log levels (DEBUG, INFO, WARNING, ERROR, SUCCESS, PHASE, AGENT)

**File**: `orchestrator/utils/logging.py`

### 6. Escalation System

When errors can't be resolved automatically, escalations are written to:
```
.workflow/escalations/{task_id}_{timestamp}.json
```

**Escalation Contents**:
- Task ID and context
- Reason for escalation
- Attempts made
- Available options
- Recommended action
- Severity level (low, medium, high, critical)

### 7. Rate Limiting

| Service | RPM | TPM | Hourly Cost Limit |
|---------|-----|-----|-------------------|
| Claude | 60 | 100K | $10 |
| Gemini | 60 | 200K | $15 |

**File**: `orchestrator/sdk/rate_limiter.py`

**Features**:
- Token bucket algorithm
- Exponential backoff on throttle
- Cost tracking per day/hour
- Concurrent request support

### 8. UI System

| Mode | Description |
|------|-------------|
| Interactive | Rich-based terminal UI with progress bars, task tree, metrics |
| Plaintext | Simple timestamped output for CI/headless environments |

**Auto-detection**: Detects CI environment variables, NO_COLOR, TTY status

**File**: `orchestrator/ui/`

---

## Workflow Phases

| Phase | Name | Description |
|-------|------|-------------|
| 1 | Planning | Claude generates implementation plan from PRODUCT.md |
| 2 | Validation | Cursor + Gemini review plan in parallel |
| 3 | Implementation | Worker Claude implements tasks with TDD |
| 4 | Verification | Cursor + Gemini review code in parallel |
| 5 | Completion | Generate summary, cleanup |

---

## File Structure

```
.workflow/
├── state.json                    # Current workflow state
├── checkpoints.db                # LangGraph checkpoints (SQLite)
├── coordination.log              # Plain text logs
├── coordination.jsonl            # JSON logs for analysis
├── escalations/                  # Escalation requests
│   └── {task_id}_{timestamp}.json
├── task_clarifications/          # Human clarification requests
│   └── {task_id}_request.json
├── issue_mapping.json            # Linear issue ID mapping
└── phases/
    ├── planning/
    │   └── plan.json
    ├── validation/
    │   ├── cursor_feedback.json
    │   └── gemini_feedback.json
    ├── task_breakdown/
    │   └── tasks.json
    ├── task_implementation/
    │   └── {task_id}_result.json
    ├── task_verification/
    │   └── {task_id}_verification.json
    ├── verification/
    │   ├── cursor_review.json
    │   └── gemini_review.json
    └── completion/
        └── summary.json
```

---

## Debugging Guide

### 1. Check Workflow Status
```bash
./scripts/init.sh status <project-name>
# or
python -m orchestrator --project <name> --status
```

### 2. View Log Files

**Human-readable logs**:
```bash
tail -f projects/<name>/.workflow/coordination.log
```

**Machine-parseable logs** (for analysis):
```bash
cat projects/<name>/.workflow/coordination.jsonl | jq
```

### 3. Check Escalations

When workflow pauses for human input:
```bash
cat projects/<name>/.workflow/escalations/*.json | jq
```

Each escalation file contains:
- `task_id`: Which task failed
- `reason`: Why it failed
- `context`: Full error context
- `attempts_made`: How many retries occurred
- `options`: Suggested actions
- `recommendation`: What the system recommends
- `severity`: How critical the issue is

### 4. Resume After Fixing Issues
```bash
python -m orchestrator --project <name> --resume
```

### 5. Reset and Retry
```bash
# Reset all phases
python -m orchestrator --project <name> --reset

# Reset specific phase
python -m orchestrator --project <name> --reset --phase 3
```

### 6. Rollback to Previous State
```bash
python -m orchestrator --project <name> --rollback 3
```

---

## Common Issues and Solutions

### Issue: "PRODUCT.md validation failed"
**Cause**: PRODUCT.md doesn't meet minimum requirements
**Solution**: Ensure PRODUCT.md has:
- Feature Name (5-100 chars)
- Summary (50-500 chars)
- Problem Statement (min 100 chars)
- At least 3 acceptance criteria with `- [ ]` items
- At least 2 Example Inputs/Outputs with code blocks
- No placeholders like `[TODO]`, `[TBD]`

### Issue: "Agent failed on both primary and backup CLI"
**Cause**: Both Claude and fallback CLI failed
**Solution**:
1. Check escalation file for detailed error
2. Verify CLI tools are working: `./scripts/init.sh check`
3. Check rate limits haven't been exceeded

### Issue: "Max iterations exceeded"
**Cause**: Task couldn't be completed in allowed retries
**Solution**:
1. Check escalation for specific failure reason
2. Review the feedback from reviewers
3. Consider breaking task into smaller subtasks

### Issue: "Review conflict unresolved"
**Cause**: Cursor and Gemini disagree and weights don't resolve
**Solution**:
1. Check escalation for both reviews
2. Make manual decision on which reviewer to follow
3. Resume workflow with decision

### Issue: "Tests failing after implementation"
**Cause**: Implementation doesn't pass TDD tests
**Solution**:
1. Check `.workflow/phases/task_verification/{task_id}_verification.json`
2. Review test output for specific failures
3. Worker will auto-retry up to 3 times

---

## Test Coverage

| Module | Tests | Status |
|--------|-------|--------|
| Agent Registry | 19 | Passing |
| Review Cycle | 17 | Passing |
| Cleanup & Recovery | 16 | Passing |
| SDK Rate Limiter | 46 | Passing |
| UI System | 38 | Passing |
| LangGraph Workflow | 150+ | Passing |
| Orchestrator | 12 | Passing |
| Validators | 20+ | Passing |
| Git Worktree | 18 | Passing |
| **Total** | **765** | **All Passing** |

Run tests:
```bash
.venv/bin/python -m pytest tests/ -v
```

---

## Commands Reference

### Initialize Project
```bash
./scripts/init.sh init <project-name>
```

### Run Workflow
```bash
# Nested project
./scripts/init.sh run <project-name>

# External project
./scripts/init.sh run --path /path/to/project

# With parallel workers
./scripts/init.sh run <project-name> --parallel 3
```

### Check Status
```bash
./scripts/init.sh status <project-name>
```

### Python CLI
```bash
python -m orchestrator --project <name> --start
python -m orchestrator --project <name> --resume
python -m orchestrator --project <name> --status
python -m orchestrator --project <name> --reset
python -m orchestrator --project <name> --rollback 3
python -m orchestrator --project-path /external/path --start
```

---

## Integration Points

### Linear.com (Optional)
Configure in `.project-config.json`:
```json
{
  "integrations": {
    "linear": {
      "enabled": true,
      "team_id": "TEAM123"
    }
  }
}
```

Tasks are synced to Linear issues for project tracking.

### Git Auto-Commit
Enable to automatically commit after each phase:
```python
Orchestrator(project_dir, auto_commit=True)
```

---

## Performance Notes

- **Parallel validation**: Cursor and Gemini run simultaneously in Phase 2 and Phase 4
- **Task-based execution**: Features broken into small tasks for incremental verification
- **Rate limiting**: Built-in to prevent API overuse
- **Checkpoint/Resume**: Workflow can be resumed from any interruption point

---

## Security Features

- **Secrets Redaction**: Automatic in all logs
- **File Boundary Enforcement**: Orchestrator cannot write to src/, tests/, etc.
- **Security-First Review**: Security issues take priority in conflict resolution
- **No Auto-Fix for Security**: Blocking security issues always escalate
