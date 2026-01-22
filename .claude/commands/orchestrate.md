---
description: Start or resume the 5-phase multi-agent workflow
allowed-tools: ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "Task", "TodoWrite"]
---

# Multi-Agent Workflow Orchestration (Optimized)

Start or resume the 5-phase workflow using native Claude Code features for 70% token efficiency.

## Architecture

```
Claude Code (This Session = Orchestrator)
    |
    +-- Task Tool --> Worker Claude (planning, implementation)
    |
    +-- Bash Tool --> cursor-agent CLI (security review)
    |
    +-- Bash Tool --> gemini CLI (architecture review)
    |
    +-- Read/Write --> .workflow/state.json (state persistence)
```

## Quick Start

```bash
# Initialize a new project
./scripts/init.sh init my-feature

# User adds:
# - Documents/ with product vision
# - PRODUCT.md (feature specification)
# - CLAUDE.md (coding standards)

# Start workflow
/orchestrate --project my-feature
```

## Workflow Phases

| Phase | Name | Agent(s) | Method |
|-------|------|----------|--------|
| 0 | Discussion | Claude | Direct conversation |
| 1 | Planning | Claude Worker | **Task tool** (70% cheaper) |
| 2 | Validation | Cursor + Gemini | **Bash** (parallel) |
| 3 | Implementation | Claude Workers | **Task tool** per task |
| 4 | Verification | Cursor + Gemini | **Bash** (parallel) |
| 5 | Completion | Claude | Direct |

## Instructions

### 1. Load Project Context

```
Read: projects/<name>/PRODUCT.md
Read: projects/<name>/Documents/ (if exists)
Read: projects/<name>/.workflow/state.json (if exists)
```

### 2. Initialize or Resume State

**New workflow**:
```json
{
  "project_name": "<name>",
  "project_dir": "projects/<name>",
  "current_phase": 0,
  "phase_status": {
    "discussion": "pending",
    "planning": "pending",
    "validation": "pending",
    "implementation": "pending",
    "verification": "pending",
    "completion": "pending"
  },
  "tasks": [],
  "errors": [],
  "updated_at": "<timestamp>"
}
```

**Resume**: Continue from `current_phase`.

### 3. Execute Phases

#### Phase 0: Discussion
- Gather requirements through conversation
- Document preferences in `CONTEXT.md`
- Update state: `discussion = "completed"`

#### Phase 1: Planning
Use **Task tool** for worker:

```
Task(
  subagent_type="Plan",
  prompt="Create implementation plan for PRODUCT.md...",
  run_in_background=false
)
```

Save to `.workflow/phases/planning/plan.json`.

#### Phase 2: Validation
Run **Bash** commands in parallel:

```bash
# Cursor (security)
cursor-agent --print --output-format json "Review plan for security..." \
  > .workflow/phases/validation/cursor-feedback.json

# Gemini (architecture)
gemini --yolo "Review plan for architecture..." \
  > .workflow/phases/validation/gemini-feedback.json
```

**Approval**: Both score >= 6.0, no blocking issues.

#### Phase 3: Implementation
For each task, use **Task tool**:

```
Task(
  subagent_type="general-purpose",
  prompt="Implement task T1 with TDD...",
  run_in_background=false
)
```

#### Phase 4: Verification
Run **Bash** commands in parallel:

```bash
# Cursor (code review)
cursor-agent --print --output-format json "Review implementation..." \
  > .workflow/phases/verification/cursor-review.json

# Gemini (architecture)
gemini --yolo "Review architecture compliance..." \
  > .workflow/phases/verification/gemini-review.json
```

**Approval**: BOTH agents must approve, score >= 7.0.

#### Phase 5: Completion
- Generate summary
- Create UAT documents
- Update final state

### 4. State Management

After each phase transition:
```
Write: .workflow/state.json
{
  "current_phase": <new_phase>,
  "phase_status": { ... },
  "updated_at": "<timestamp>"
}
```

## Token Efficiency

| Component | Old | New | Savings |
|-----------|-----|-----|---------|
| Worker spawn | ~13k | ~4k | **70%** |
| Context pass | Full dup | Filtered | **60%** |
| 10 task project | ~130k | ~40k | **69%** |

## Related Skills

- `/plan-feature` - Phase 1 details
- `/validate-plan` - Phase 2 details
- `/implement-task` - Phase 3 details
- `/verify-code` - Phase 4 details
- `/resolve-conflict` - Conflict resolution
- `/phase-status` - Check progress
- `/call-cursor` - Cursor wrapper
- `/call-gemini` - Gemini wrapper

## Multi-Agent Review (Preserved)

Every phase is reviewed by multiple agents:

```
Planning → Cursor (security) + Gemini (architecture)
Implementation → Per-task verification
Code → Cursor (security audit) + Gemini (design review)
```

**Nothing changes about multi-agent review** - same agents, same thresholds, same conflict resolution. Only the orchestration method is optimized.
