#!/bin/bash
# Multi-Agent Orchestration System - Project Initialization Script
# Usage: bash init-multi-agent.sh [project-dir]
#
# This script sets up a target project for multi-agent orchestration where
# Claude Code acts as the live orchestrator, coordinating with Cursor and
# Gemini agents via CLI calls.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
META_ARCHITECT_DIR="$(dirname "$SCRIPT_DIR")"

# Project directory (default: current directory)
PROJECT_DIR="${1:-.}"

# Create project directory if it doesn't exist
mkdir -p "$PROJECT_DIR"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Multi-Agent Orchestration System Setup${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} $1 found"
        return 0
    else
        echo -e "  ${YELLOW}⚠${NC} $1 not found"
        return 1
    fi
}

# Check optional CLIs (just informational)
check_command claude || echo -e "    ${YELLOW}Claude CLI recommended for orchestration${NC}"
check_command cursor-agent || echo -e "    ${YELLOW}Install with: npm install -g @anthropic/cursor-agent${NC}"
check_command gemini || echo -e "    ${YELLOW}Install with: npm install -g @google/gemini-cli${NC}"

echo ""
echo -e "${YELLOW}Initializing project in: ${PROJECT_DIR}${NC}"
echo ""

# Create directory structure
echo -e "${YELLOW}Creating directory structure...${NC}"

mkdir -p "$PROJECT_DIR/.workflow/phases/planning"
mkdir -p "$PROJECT_DIR/.workflow/phases/validation"
mkdir -p "$PROJECT_DIR/.workflow/phases/implementation"
mkdir -p "$PROJECT_DIR/.workflow/phases/verification"
mkdir -p "$PROJECT_DIR/.workflow/phases/completion"
mkdir -p "$PROJECT_DIR/.workflow/progress"
mkdir -p "$PROJECT_DIR/.workflow/checkpoints"
mkdir -p "$PROJECT_DIR/.claude/commands"
mkdir -p "$PROJECT_DIR/.claude/skills"
mkdir -p "$PROJECT_DIR/.cursor"
mkdir -p "$PROJECT_DIR/scripts"

echo -e "  ${GREEN}✓${NC} Created .workflow directory structure"
echo -e "  ${GREEN}✓${NC} Created .workflow/progress for agentic memory"
echo -e "  ${GREEN}✓${NC} Created .workflow/checkpoints for resumption"

# Copy templates
echo -e "${YELLOW}Setting up templates...${NC}"

# AGENTS.md (cross-CLI rules)
if [ ! -f "$PROJECT_DIR/AGENTS.md" ]; then
    cp "$META_ARCHITECT_DIR/templates/AGENTS.md.template" "$PROJECT_DIR/AGENTS.md"
    echo -e "  ${GREEN}✓${NC} Created AGENTS.md"
else
    echo -e "  ${YELLOW}⚠${NC} AGENTS.md already exists, skipping"
fi

# PRODUCT.md (if not exists)
if [ ! -f "$PROJECT_DIR/PRODUCT.md" ]; then
    cp "$META_ARCHITECT_DIR/templates/PRODUCT.md.template" "$PROJECT_DIR/PRODUCT.md"
    echo -e "  ${GREEN}✓${NC} Created PRODUCT.md (please edit with your feature spec)"
else
    echo -e "  ${YELLOW}⚠${NC} PRODUCT.md already exists, skipping"
fi

# Claude context
if [ ! -f "$PROJECT_DIR/.claude/system.md" ]; then
    if [ -f "$META_ARCHITECT_DIR/templates/claude/system.md.template" ]; then
        cp "$META_ARCHITECT_DIR/templates/claude/system.md.template" "$PROJECT_DIR/.claude/system.md"
        echo -e "  ${GREEN}✓${NC} Created .claude/system.md"
    fi
fi

# Cursor rules
if [ ! -f "$PROJECT_DIR/.cursor/rules" ]; then
    cp "$META_ARCHITECT_DIR/templates/cursor/rules.template" "$PROJECT_DIR/.cursor/rules"
    echo -e "  ${GREEN}✓${NC} Created .cursor/rules"
fi

# Gemini context
if [ ! -f "$PROJECT_DIR/GEMINI.md" ]; then
    cp "$META_ARCHITECT_DIR/templates/gemini/GEMINI.md.template" "$PROJECT_DIR/GEMINI.md"
    echo -e "  ${GREEN}✓${NC} Created GEMINI.md"
fi

# CLAUDE.md - Minimal stub referencing AGENTS.md as source of truth
if [ ! -f "$PROJECT_DIR/CLAUDE.md" ]; then
    cat > "$PROJECT_DIR/CLAUDE.md" << 'EOF'
# Claude Code Context

<!-- Source of truth: AGENTS.md -->
<!-- This file contains Claude-specific extensions only -->
<!-- Models: GPT-5.2-Codex (Cursor), Gemini 3 Pro (Gemini) -->

This project uses a **multi-agent orchestration system**. For complete workflow rules, read `AGENTS.md`.

## Quick Reference

| Resource | Purpose |
|----------|---------|
| `AGENTS.md` | Complete workflow rules (READ THIS FIRST) |
| `PRODUCT.md` | Feature specification |
| `.workflow/state.json` | Workflow state and progress |
| `.workflow/progress/` | Agentic memory / progress files |

## Your Role

You are the **lead orchestrator**. Coordinate the workflow by:
1. Reading PRODUCT.md and creating plans
2. Invoking Cursor/Gemini via `scripts/call-*.sh`
3. Processing JSON feedback
4. Implementing with TDD
5. Iterating until all agents approve

## Agent Invocation

```bash
# Cursor (code quality, security) - GPT-5.2-Codex
bash scripts/call-cursor.sh <prompt-file> <output-file>

# Gemini (architecture, scalability) - Gemini 3 Pro
bash scripts/call-gemini.sh <prompt-file> <output-file>
```

## Model Override

```bash
# Override default models via environment variables
export CURSOR_MODEL=gpt-5.1-codex     # Options: gpt-5.2-codex, gpt-5.1-codex, gpt-4.5-turbo
export GEMINI_MODEL=gemini-3-flash    # Options: gemini-3-pro, gemini-3-flash, gemini-2.5-pro
```

## Session Resumption

When resuming a workflow:
1. Read `.workflow/progress/handoff-notes.md` first
2. Check `.workflow/state.json` for current phase
3. Read `.workflow/progress/current-task.md` for active work

## Claude-Specific Notes

- Always read AGENTS.md for the full protocol
- Context files are version-tracked for drift detection
- Approval requires consensus (see AGENTS.md for policies)
- Use progress files to maintain context across sessions
EOF
    echo -e "  ${GREEN}✓${NC} Created CLAUDE.md"
fi

# Copy bash scripts for CLI invocation
echo -e "${YELLOW}Setting up CLI scripts...${NC}"

cp "$META_ARCHITECT_DIR/scripts/call-cursor.sh" "$PROJECT_DIR/scripts/"
cp "$META_ARCHITECT_DIR/scripts/call-gemini.sh" "$PROJECT_DIR/scripts/"
chmod +x "$PROJECT_DIR/scripts/call-cursor.sh"
chmod +x "$PROJECT_DIR/scripts/call-gemini.sh"
echo -e "  ${GREEN}✓${NC} Created scripts/call-cursor.sh"
echo -e "  ${GREEN}✓${NC} Created scripts/call-gemini.sh"

# Copy prompt templates
echo -e "${YELLOW}Setting up prompt templates...${NC}"

mkdir -p "$PROJECT_DIR/scripts/prompts"
if [ -d "$META_ARCHITECT_DIR/templates/prompts" ]; then
    cp "$META_ARCHITECT_DIR/templates/prompts/"*.md "$PROJECT_DIR/scripts/prompts/" 2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} Copied prompt templates to scripts/prompts/"
fi

# Initialize workflow state
echo -e "${YELLOW}Initializing workflow state...${NC}"

if [ ! -f "$PROJECT_DIR/.workflow/state.json" ]; then
    cat > "$PROJECT_DIR/.workflow/state.json" << 'EOF'
{
  "current_phase": 1,
  "phase_status": {
    "1": "not_started",
    "2": "not_started",
    "3": "not_started",
    "4": "not_started",
    "5": "not_started"
  },
  "iteration_count": 0,
  "last_updated": null,
  "agents_status": {
    "claude": "idle",
    "cursor": "pending",
    "gemini": "pending"
  },
  "feature": null,
  "context": {
    "files": {},
    "captured_at": null,
    "version": "2.0"
  },
  "models": {
    "cursor": "gpt-5.2-codex",
    "gemini": "gemini-3-pro"
  }
}
EOF
    echo -e "  ${GREEN}✓${NC} Created .workflow/state.json"
fi

# Initialize progress files
echo -e "${YELLOW}Initializing progress files...${NC}"

if [ ! -f "$PROJECT_DIR/.workflow/progress/handoff-notes.md" ]; then
    cat > "$PROJECT_DIR/.workflow/progress/handoff-notes.md" << 'EOF'
# Session Handoff Notes
## Generated: Initial Setup

## Workflow State
- **Current Phase**: 1 (Planning)
- **Status**: Not Started

## Completed Work
- [x] Project initialized with multi-agent orchestration

## In Progress
- [ ] Awaiting feature specification in PRODUCT.md

## Recommended Next Steps
1. Edit PRODUCT.md with your feature specification
2. Start Claude Code and request implementation
3. Follow the 5-phase workflow

## Important Context
This is a fresh project setup. No workflow has been started yet.

## Files to Read First
1. `PRODUCT.md` - Feature specification (needs editing)
2. `AGENTS.md` - Complete workflow rules
3. `.workflow/state.json` - Workflow state
EOF
    echo -e "  ${GREEN}✓${NC} Created initial handoff-notes.md"
fi

# Add .gitignore entries
GITIGNORE="$PROJECT_DIR/.gitignore"
if [ ! -f "$GITIGNORE" ]; then
    touch "$GITIGNORE"
fi

# Add workflow-related ignores if not present
if ! grep -q ".workflow/coordination.log" "$GITIGNORE" 2>/dev/null; then
    cat >> "$GITIGNORE" << 'EOF'

# Multi-Agent Orchestration
.workflow/coordination.log
.workflow/coordination.jsonl
__pycache__/
*.pyc
EOF
    echo -e "  ${GREEN}✓${NC} Updated .gitignore"
fi

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "${YELLOW}Project structure created:${NC}"
echo ""
echo -e "  ${BLUE}$PROJECT_DIR/${NC}"
echo -e "  ├── PRODUCT.md          ${YELLOW}← Edit with your feature spec${NC}"
echo -e "  ├── AGENTS.md           ${YELLOW}← Workflow rules (read-only)${NC}"
echo -e "  ├── CLAUDE.md           ${YELLOW}← Claude context${NC}"
echo -e "  ├── GEMINI.md           ${YELLOW}← Gemini context${NC}"
echo -e "  ├── .cursor/rules       ${YELLOW}← Cursor rules${NC}"
echo -e "  ├── scripts/"
echo -e "  │   ├── call-cursor.sh  ${YELLOW}← Invoke Cursor CLI (GPT-5.2-Codex)${NC}"
echo -e "  │   ├── call-gemini.sh  ${YELLOW}← Invoke Gemini CLI (Gemini 3 Pro)${NC}"
echo -e "  │   └── prompts/        ${YELLOW}← Prompt templates${NC}"
echo -e "  └── .workflow/"
echo -e "      ├── state.json      ${YELLOW}← Workflow state${NC}"
echo -e "      ├── progress/       ${YELLOW}← Agentic memory / handoff notes${NC}"
echo -e "      ├── checkpoints/    ${YELLOW}← Resumable checkpoints${NC}"
echo -e "      └── phases/         ${YELLOW}← Phase artifacts${NC}"
echo ""
echo -e "${YELLOW}Default Models (January 2026):${NC}"
echo -e "  • Cursor: ${BLUE}GPT-5.2-Codex${NC} (256K context)"
echo -e "  • Gemini: ${BLUE}Gemini 3 Pro${NC} (1M+ context)"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo ""
echo -e "  1. Edit ${BLUE}PRODUCT.md${NC} with your feature specification"
echo ""
echo -e "  2. Start Claude Code in the project:"
echo -e "     ${BLUE}cd $PROJECT_DIR${NC}"
echo -e "     ${BLUE}claude${NC}"
echo ""
echo -e "  3. Ask Claude to implement your feature:"
echo -e "     ${BLUE}\"Implement the feature described in PRODUCT.md using the multi-agent workflow\"${NC}"
echo ""
echo -e "${YELLOW}How it works:${NC}"
echo -e "  Claude Code reads PRODUCT.md, creates a plan, calls Cursor and"
echo -e "  Gemini for validation via the bash scripts, implements the code,"
echo -e "  and iterates based on their feedback until all agents approve."
echo ""
echo -e "${YELLOW}Session Resumption:${NC}"
echo -e "  Progress is automatically saved to .workflow/progress/"
echo -e "  Read handoff-notes.md when resuming a session."
echo ""
