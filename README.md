# Multi-Agent Development System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

A **live multi-agent orchestration system** where Claude Code acts as the lead orchestrator, coordinating with Cursor and Gemini agents via CLI to implement features through a structured 5-phase workflow.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Workflow Phases](#workflow-phases)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Orchestrator Library](#orchestrator-library)
- [CLI Usage](#cli-usage)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Overview

This system implements a robust multi-agent development workflow that leverages the strengths of different AI coding assistants:

| Agent | Role | Specialization |
|-------|------|----------------|
| **Claude Code** | Lead Orchestrator | Planning, implementation, coordination |
| **Cursor Agent** | Code Reviewer | Security, code quality, bug detection |
| **Gemini Agent** | Architecture Reviewer | Scalability, design patterns, system health |

### Key Principles

- **Live orchestration**: Claude Code coordinates in real-time, not a standalone script
- **Agent specialization**: Each agent handles tasks matching their strengths
- **Parallel reviews**: Validation and verification run Cursor + Gemini in parallel
- **Iterative workflow**: Feedback loops ensure quality before proceeding
- **TDD approach**: Tests first, then implementation
- **Context versioning**: Track changes to context files with drift detection

## Features

### Core Capabilities

- **5-Phase Workflow**: Planning → Validation → Implementation → Verification → Completion
- **Parallel Execution**: Cursor and Gemini run validation/verification concurrently
- **TDD Emphasis**: Tests are written before implementation in Phase 3
- **State Persistence**: Full workflow state with resumability
- **Auto-commit**: Optional git commits after each phase

### Advanced Features (v1.1)

| Feature | Description |
|---------|-------------|
| **Context Versioning** | SHA-256 checksums for detecting changes to context files |
| **Approval Policies** | Configurable policies (NO_BLOCKERS, ALL_MUST_APPROVE, WEIGHTED_SCORE, MAJORITY) |
| **Conflict Resolution** | Weighted expertise-based resolution when agents disagree |
| **Iteration Tracking** | Track plan-validate-implement cycles |
| **Drift Detection** | Automatic warning when context files change mid-workflow |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Claude Code (Orchestrator)                   │
│  - Reads PRODUCT.md for requirements                            │
│  - Creates implementation plans                                 │
│  - Calls Cursor/Gemini for validation                           │
│  - Implements code using TDD                                    │
│  - Iterates based on feedback                                   │
└─────────────────────────────────────────────────────────────────┘
           │                                    │
           ▼                                    ▼
┌─────────────────────┐              ┌─────────────────────┐
│   Cursor Agent      │              │   Gemini Agent      │
│   (Code Review)     │              │   (Arch Review)     │
│                     │              │                     │
│ - Security analysis │              │ - Design patterns   │
│ - Bug detection     │              │ - Scalability       │
│ - Test coverage     │              │ - System health     │
└─────────────────────┘              └─────────────────────┘
```

### Data Flow

```
Phase 1 → plan.json
  ↓
Phase 2 → cursor-feedback.json + gemini-feedback.json → consolidated-feedback.json
  ↓
Phase 3 → implementation-results.json + test-results.json
  ↓
Phase 4 → cursor-review.json + gemini-review.json → verification-results.json
  ↓
Phase 5 → completion-summary.json + WORKFLOW-SUMMARY.md
```

## Installation

### Prerequisites

- Python 3.10+
- At least one AI CLI tool:
  - Claude Code CLI (`claude`)
  - Cursor Agent CLI (`cursor-agent`) - optional
  - Gemini CLI (`gemini`) - optional

### Setup

```bash
# Clone the repository
git clone git@github.com:EtroxTaran/multi-agent-development.git
cd multi-agent-development

# (Optional) Install Python dependencies for testing
pip install pytest

# Initialize a new project
bash scripts/init-multi-agent.sh /path/to/your/project
```

## Quick Start

### 1. Initialize Your Project

```bash
bash scripts/init-multi-agent.sh ./my-project
```

This creates:
- `.workflow/` - Workflow state and phase artifacts
- `PRODUCT.md` - Template for your feature specification
- `AGENTS.md` - Cross-agent workflow rules (source of truth)
- `scripts/` - CLI invocation scripts and prompt templates
- Agent-specific context files

### 2. Define Your Feature

Edit `PRODUCT.md` with your feature specification:

```markdown
# Product Specification

## Feature Name
User Authentication System

## Summary
Implement JWT-based authentication with login, registration, and token refresh.

## Goals
- Secure user registration with email verification
- JWT token generation with configurable expiry
- Token refresh mechanism
- Password reset flow

## Technical Requirements
- Use bcrypt for password hashing
- Store tokens in HTTP-only cookies
- Implement rate limiting on auth endpoints
```

### 3. Start Orchestration

```bash
# Start Claude Code in the project
cd my-project
claude

# Ask Claude to implement the feature
> Implement the feature described in PRODUCT.md using the multi-agent workflow
```

Claude Code will orchestrate the entire workflow automatically.

## Workflow Phases

| Phase | Name | Lead | Reviewers | Output |
|-------|------|------|-----------|--------|
| 1 | Planning | Claude | - | `plan.json`, `PLAN.md` |
| 2 | Validation | Claude | Cursor, Gemini | `*-feedback.json`, `consolidated-feedback.json` |
| 3 | Implementation | Claude | - | Code + tests |
| 4 | Verification | Claude | Cursor, Gemini | `*-review.json`, `ready-to-merge.json` |
| 5 | Completion | Claude | - | `COMPLETION.md`, `metrics.json` |

### Phase Details

#### Phase 1: Planning (Claude)
- Reads `PRODUCT.md` specification
- Creates structured implementation plan
- Defines components, dependencies, test strategy
- **Output**: `plan.json`, `PLAN.md`

#### Phase 2: Validation (Cursor + Gemini, Parallel)
- Claude calls both agents via bash scripts
- **Cursor reviews**: Code quality, security, maintainability
- **Gemini reviews**: Architecture, scalability, design patterns
- Claude consolidates feedback, iterates if needed
- **Approval Policy**: NO_BLOCKERS (score ≥ 6.0)

#### Phase 3: Implementation (Claude, TDD)
- Writes tests first (expect failures)
- Implements code to make tests pass
- Runs full test suite
- **Output**: `implementation-results.json`, `test-results.json`

#### Phase 4: Verification (Cursor + Gemini, Parallel)
- Claude calls both agents for final review
- Both must approve for completion
- If issues found, fix and re-verify
- **Approval Policy**: ALL_MUST_APPROVE (score ≥ 7.0)

#### Phase 5: Completion
- Generates workflow summary
- Creates metrics report
- Updates final state
- **Output**: `COMPLETION.md`, `WORKFLOW-SUMMARY.md`

## Project Structure

After initialization:

```
your-project/
├── PRODUCT.md              # Your feature spec (edit this!)
├── AGENTS.md               # Workflow rules (source of truth)
├── CLAUDE.md               # Claude-specific context
├── GEMINI.md               # Gemini-specific context
├── .claude/
│   └── system.md           # Claude system prompt
├── .cursor/
│   └── rules               # Cursor rules
├── scripts/
│   ├── call-cursor.sh      # Invoke Cursor CLI
│   ├── call-gemini.sh      # Invoke Gemini CLI
│   └── prompts/            # Prompt templates
└── .workflow/
    ├── state.json          # Workflow state
    ├── coordination.log    # Text logs
    ├── coordination.jsonl  # JSON logs
    └── phases/
        ├── planning/       # Phase 1 outputs
        ├── validation/     # Phase 2 outputs
        ├── implementation/ # Phase 3 outputs
        ├── verification/   # Phase 4 outputs
        └── completion/     # Phase 5 outputs
```

### Meta-Architect Source Structure

```
multi-agent-development/
├── orchestrator/           # Python orchestration library
│   ├── agents/             # Agent CLI wrappers
│   ├── phases/             # Phase implementations
│   └── utils/              # Utilities (state, logging, context, approval)
├── scripts/
│   ├── init-multi-agent.sh # Project initialization
│   ├── call-cursor.sh      # Cursor CLI wrapper
│   └── call-gemini.sh      # Gemini CLI wrapper
├── templates/              # Project templates
├── schemas/                # JSON schemas
├── tests/                  # Test suite
└── examples/               # Example projects
```

## Configuration

### Approval Policies

| Policy | Description | Default Phase |
|--------|-------------|---------------|
| `NO_BLOCKERS` | Approve if no blocking issues and score meets threshold | Phase 2 |
| `ALL_MUST_APPROVE` | Both agents must explicitly approve | Phase 4 |
| `WEIGHTED_SCORE` | Weighted average of scores must meet threshold | - |
| `MAJORITY` | At least one agent must approve | - |

### Conflict Resolution Strategies

| Strategy | Description |
|----------|-------------|
| `WEIGHTED` | Prefer agent with higher expertise for the area (default) |
| `CONSERVATIVE` | Take the more cautious position |
| `OPTIMISTIC` | Take the more permissive position |
| `ESCALATE` | Require human decision |
| `DEFER_TO_LEAD` | Claude decides as orchestrator |
| `UNANIMOUS` | Both must agree, escalate if not |

### Expertise Weights

When agents disagree, resolution uses weighted expertise:

| Area | Cursor | Gemini |
|------|--------|--------|
| Security | 0.8 | 0.2 |
| Architecture | 0.3 | 0.7 |
| Code Quality | 0.7 | 0.3 |
| Scalability | 0.2 | 0.8 |
| Maintainability | 0.6 | 0.4 |
| Testing | 0.7 | 0.3 |
| Performance | 0.4 | 0.6 |

## Orchestrator Library

### Using as a Python Library

```python
from orchestrator import Orchestrator
from orchestrator.utils import (
    StateManager,
    ApprovalEngine,
    ConflictResolver,
    ContextManager,
)

# Initialize orchestrator
orch = Orchestrator(
    project_dir="/path/to/project",
    max_retries=3,
    auto_commit=True,
)

# Run full workflow
result = orch.run(start_phase=1, end_phase=5)
```

### State Management

```python
from orchestrator.utils import StateManager

state = StateManager("/path/to/project")
state.load()

# Get workflow summary
summary = state.get_summary()
print(f"Phase: {summary['current_phase']}")
print(f"Iterations: {summary['iteration_count']}")

# Track iterations
state.increment_iteration()
```

### Context Management

```python
from orchestrator.utils import ContextManager

ctx = ContextManager("/path/to/project")

# Capture initial context
context = ctx.capture_context()

# Check for drift later
drift = ctx.validate_context(context)
if drift.has_drift:
    print(f"Changed: {drift.changed_files}")
    print(ctx.get_drift_summary(drift))
```

### Custom Approval Configuration

```python
from orchestrator.utils import ApprovalEngine, ApprovalConfig, ApprovalPolicy

engine = ApprovalEngine()

# Stricter config for Phase 2
config = ApprovalConfig(
    policy=ApprovalPolicy.ALL_MUST_APPROVE,
    minimum_score=8.0,
    require_both_agents=True,
)

result = engine.evaluate_for_validation(
    cursor_feedback,
    gemini_feedback,
    config=config,
)
print(f"Approved: {result.approved}")
print(f"Reasoning: {result.reasoning}")
```

### Conflict Resolution

```python
from orchestrator.utils import ConflictResolver, ResolutionStrategy

resolver = ConflictResolver(default_strategy=ResolutionStrategy.WEIGHTED)

# Detect and resolve conflicts
result = resolver.resolve_all(cursor_feedback, gemini_feedback)
if result.has_conflicts:
    print(f"Conflicts: {len(result.conflicts)}")
    print(f"Unresolved: {result.unresolved_count}")

# Get consensus recommendation
consensus = resolver.get_consensus_recommendation(cursor_feedback, gemini_feedback)
print(f"Recommendation: {consensus['recommendation']}")
```

## CLI Usage

### Invoking Agents Directly

```bash
# Cursor (Code Review)
bash scripts/call-cursor.sh <prompt-file> <output-file> [project-dir]

# Gemini (Architecture Review)
bash scripts/call-gemini.sh <prompt-file> <output-file> [project-dir]
```

### Orchestrator CLI (Python)

```bash
# Run full workflow
python -m orchestrator --start

# Resume from specific phase
python -m orchestrator --resume --phase 3

# Check status
python -m orchestrator --status

# Reset workflow
python -m orchestrator --reset
```

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test modules
python -m pytest tests/test_context.py -v
python -m pytest tests/test_approval.py -v
python -m pytest tests/test_conflict_resolution.py -v
python -m pytest tests/test_state.py -v
python -m pytest tests/test_phases.py -v

# Run with coverage
python -m pytest tests/ --cov=orchestrator --cov-report=html
```

## Troubleshooting

### CLI Not Found

```
Error: cursor-agent CLI not found
```

Install the missing CLI:
```bash
# Cursor Agent
npm install -g @anthropic/cursor-agent

# Gemini CLI
npm install -g @google/gemini-cli
```

The workflow can proceed with available agents if not all are installed.

### Context Drift Detected

```
WARNING: Context drift detected in phase 2
  Modified: agents
```

This means AGENTS.md or another tracked file changed mid-workflow. Options:
- Continue (default): Warning is logged, workflow proceeds
- Block: Set `block_on_drift=True` in phase configuration
- Sync: Call `state.sync_context()` to update checksums

### Agent Feedback Requires Changes

Claude will automatically:
1. Read the feedback
2. Update the plan/code
3. Re-submit for review
4. Track iteration count

### Max Iterations Reached

After 3 iterations without approval:
- Claude will summarize the issues
- Ask for human guidance
- Options: continue, abort, or modify approach

### Workflow Stuck

```bash
# Check current state
python -m orchestrator --status

# Reset specific phase
python -m orchestrator --reset-phase 2

# Full reset
python -m orchestrator --reset
```

## JSON Schemas

All data structures are validated against schemas in `schemas/`:

| Schema | Purpose |
|--------|---------|
| `state-schema.json` | Workflow state structure |
| `plan-schema.json` | Implementation plan format |
| `feedback-schema.json` | Agent feedback format |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`python -m pytest tests/ -v`)
5. Commit (`git commit -m 'Add amazing feature'`)
6. Push (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with Claude Code, Cursor, and Gemini
- Inspired by multi-agent orchestration patterns from industry research
- Follows 2025-2026 best practices for AI-assisted development

---

**Note**: This system requires access to AI CLI tools. Ensure you have the appropriate API keys configured before use.
