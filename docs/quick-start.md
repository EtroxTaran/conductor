# QUICK START: Multi-Agent Orchestration System
## Everything You Need to Know to Get Started

**Date**: January 2026
**For**: AI Coding Agents & Development Teams

---

## THE BIG PICTURE

### What You're Building
A system where **Claude Code, Cursor, and Gemini CLI** all run in the **same project folder**, sharing complete context through files, and coordinating through a **5-phase workflow**:

```
PRODUCT.md (Vision) 
    ↓
Phase 1: PLANNING (Claude) → plan.json
    ↓
Phase 2: VALIDATION (Cursor + Gemini parallel) → feedback.json
    ↓
Phase 3: IMPLEMENTATION (Claude) → code + tests
    ↓
Phase 4: VERIFICATION (Cursor + Gemini parallel) → approvals
    ↓
Phase 5: COMPLETION (Orchestrator) → ready for merge
    ↓
[Loop back to PRODUCT.md for next feature]
```

**Key Insight**: No context loss. All agents in same folder. File-system-as-state.

---

## WHAT YOU GET

### 1. **Initialization Script** (`init-multi-agent.sh`)
- Sets up directory structure (.workflow/, .claude/, .cursor/, .gemini/)
- Creates configuration files for each CLI
- Generates shared AGENTS.md
- Creates PRODUCT.md template
- One-command setup: `bash init-multi-agent.sh my-project`

### 2. **Configuration Templates**
- `.claude/system.md` - Claude's system prompt
- `.cursor/rules` - Cursor's project rules
- `.gemini/GEMINI.md` - Gemini's identity
- `AGENTS.md` - Shared definitions all agents read
- `.rules/` - Shared project rules

### 3. **Orchestrator Script** (`.workflow/orchestrator.py`)
- Manages 5-phase workflow
- Coordinates agent invocations
- Tracks state in `.workflow/state.json`
- Handles parallel execution
- Logs everything to `.workflow/coordination.log`

### 4. **Workflow Structure** (`.workflow/phases/`)
Each phase has its own directory with outputs, feedback, and logs:
```
.workflow/phases/
├── 01-planning/
│   ├── plan.json (structure: tasks, dependencies, risks)
│   ├── PLAN.md (human-readable)
│   └── claude-output.log
├── 02-test-design/
│   ├── cursor-feedback.json
│   ├── gemini-validation.json
│   ├── consolidated-feedback.md
│   └── *.log files
├── 03-implementation/
│   ├── implementation.md
│   ├── test-results.json (status: ALL_PASSING, coverage: 86%)
│   ├── code-changes.json
│   └── implementation-log.md
├── 04-verification/
│   ├── cursor-review.json (verdict: approved)
│   ├── gemini-review.json (verdict: approved)
│   ├── ready-to-merge.json
│   └── *.log files
└── 05-completion/
    ├── summary.json
    └── metrics.json
```

---

## HOW SHARED CONTEXT WORKS

### All Agents Read From:

1. **PRODUCT.md** (Your Vision)
   ```markdown
   # Current Goal: Implement JWT Auth
   
   ## Acceptance Criteria
   - User registration
   - Login returns JWT tokens
   - Tokens refresh automatically
   
   ## Phase Progress
   - [ ] Phase 1: Planning
   - [ ] Phase 2: Validation
   - [ ] Phase 3: Implementation
   - [ ] Phase 4: Verification
   - [ ] Phase 5: Complete
   ```

2. **Shared Rules**
   - `.rules/base-rules.md` → All agents
   - `.rules/architecture.md` → All agents
   - `AGENTS.md` → Agent role definitions
   - Project-specific: `.claude/rules/`, `.cursor/rules`, `.gemini/GEMINI.md`

3. **Previous Phase Outputs**
   - Each agent reads: `.workflow/phases/{current}/`
   - Each agent reads feedback: `.workflow/phases/{current}/feedback.json`
   - Each agent produces: `.workflow/phases/{current}/output.json`

### Key Files Each Agent Reads:
- `PRODUCT.md` (vision/goals)
- `AGENTS.md` (role definitions)
- `.workflow/state.json` (current phase)
- `.workflow/phases/*/` (previous outputs)
- Project rules and configurations
- Source code (inherited from working directory)

### No Context Resets
Because all CLIs run in the same folder, they inherit the project context automatically. No need to pass code or context explicitly.

---

## THE 5-PHASE WORKFLOW EXPLAINED

### Phase 1: PLANNING (Claude Code - ~5 min)
**Claude reads PRODUCT.md and creates a plan**

```bash
claude -p "Read PRODUCT.md. Create plan.json with tasks, dependencies, risks" \
  --append-system-prompt-file=.claude/system.md
```

**Outputs**:
- `.workflow/phases/01-planning/plan.json` - Structured task list
- `.workflow/phases/01-planning/PLAN.md` - Human-readable

**Example Output**:
```json
{
  "phase": "planning",
  "feature": "JWT Authentication",
  "tasks": [
    {"id": "t1", "title": "Create User model", "dependencies": [], "test_strategy": "Unit tests"},
    {"id": "t2", "title": "Implement login", "dependencies": ["t1"], "test_strategy": "Integration tests"}
  ],
  "dependency_graph": {"t2": ["t1"], "t3": ["t1", "t2"]},
  "risks": ["Token expiration edge cases"],
  "completion_criteria": "All tests pass, no security issues"
}
```

---

### Phase 2: VALIDATION (Cursor + Gemini Parallel - ~10 min)
**Both agents review the plan simultaneously**

```bash
# Cursor reviews for code/logic quality
cursor-agent -p "Review plan at .workflow/phases/01-planning/plan.json" --rules .cursor/rules &

# Gemini validates architecture
gemini -p "Validate plan at .workflow/phases/01-planning/plan.json" -e validator-agent &

wait  # Wait for both
```

**Outputs**:
- `.workflow/phases/02-test-design/cursor-feedback.json` - Code quality review
- `.workflow/phases/02-test-design/gemini-validation.json` - Architecture validation
- `.workflow/phases/02-test-design/consolidated-feedback.md` - Merged feedback

**Example Feedback**:
```json
{
  "cursor_verdict": "revision_required",
  "cursor_score": 78,
  "critical_issues": [
    "Missing rate limiting for brute force protection"
  ],
  "gemini_verdict": "approved",
  "gemini_score": 92,
  "next_action": "claude_refines_plan"
}
```

**If Either Agent Says "blocked"**: Claude reads feedback and refines plan (loop back)
**If Both "approved"**: Move to Phase 3

---

### Phase 3: IMPLEMENTATION (Claude Code - ~20 min)
**Claude implements tests first (TDD), then code**

```bash
claude -p "
Read refined plan. 
Write tests first (TDD).
Implement to pass tests.
Run npm test.
Save results to .workflow/phases/03-implementation/
" --append-system-prompt-file=.claude/system.md --continue
```

**Outputs**:
- Test files in `spec/` or `__tests__/`
- Implementation in `src/`
- `.workflow/phases/03-implementation/test-results.json` - Test status
- `.workflow/phases/03-implementation/implementation-log.md` - What was done

**Example Test Results**:
```json
{
  "total_tests": 42,
  "passed": 42,
  "failed": 0,
  "coverage": 86,
  "status": "ALL_PASSING"
}
```

**Key Rule**: No code without tests. Tests must pass before moving forward.

---

### Phase 4: VERIFICATION (Cursor + Gemini Parallel - ~10 min)
**Both agents do final review**

```bash
# Cursor: Code quality final check
cursor-agent -p "Final code quality review" --rules .cursor/rules &

# Gemini: Test completeness and validation
gemini -p "Verify tests complete and implementation sound" -e validator-agent &

wait
```

**Outputs**:
- `.workflow/phases/04-verification/cursor-review.json` - Approved/revision/blocked
- `.workflow/phases/04-verification/gemini-review.json` - Approved/revision/blocked
- `.workflow/phases/04-verification/ready-to-merge.json` - IF both approved

**Example Approvals**:
```json
{
  "cursor_verdict": "approved",
  "cursor_score": 94,
  "approved_by_cursor": true,
  "gemini_verdict": "approved",
  "architecture_valid": true,
  "tests_passing": true,
  "approved_by_gemini": true,
  "status": "READY_FOR_MERGE"
}
```

**If Either Agent Says "revision_required"**: Claude reads feedback and implements fixes
**If Either Agent Says "blocked"**: Workflow stops, user intervention needed
**If Both "approved"**: Move to Phase 5

---

### Phase 5: COMPLETION (Orchestrator - ~2 min)
**Wrap up, create summary, ready for next feature**

```bash
# Orchestrator creates completion summary
cat .workflow/phases/05-completion/summary.json
{
  "status": "WORKFLOW_COMPLETE",
  "phases_completed": 5,
  "next_steps": "Review PRODUCT.md for next feature"
}

# Feature is merged to main
git add -A && git commit -m "feat: Complete JWT auth implementation"
```

**Update PRODUCT.md for next feature**:
```markdown
# Previous: Implement JWT Auth - ✅ COMPLETE

## Current Goal: Add Multi-Factor Authentication (MFA)
[Next feature details...]
```

**Re-run orchestrator for next feature**
```bash
python .workflow/orchestrator.py --start
```

---

## ACTUAL USAGE: STEP-BY-STEP

### 1. Initialize Project (One-Time)

```bash
# Download and run initialization script
curl -fsSL https://your-host/init-multi-agent.sh | bash -s -- my-project

# Script creates:
# - .workflow/ directory with phases, schemas, logs
# - .claude/, .cursor/, .gemini/ with configs
# - AGENTS.md, PRODUCT.md templates
# - .gitignore entries
# - Git repository initialized

cd my-project
```

### 2. Define Your Feature (Update PRODUCT.md)

```bash
# Edit PRODUCT.md with your feature goal
cat > PRODUCT.md << 'EOF'
# JWT Authentication Service

## Feature
Users can register, login, and get JWT tokens that refresh automatically.

## Acceptance Criteria
- [ ] User registration with email validation
- [ ] Login returns JWT access + refresh tokens
- [ ] Token refresh without re-login
- [ ] Tokens expire correctly
- [ ] Rate limiting prevents brute force
- [ ] All tests pass (85%+ coverage)

## Tech Stack
- TypeScript + Express
- PostgreSQL
- Jest testing

---

## Phase Checklist
- [ ] Phase 1: Planning
- [ ] Phase 2: Validation
- [ ] Phase 3: Implementation
- [ ] Phase 4: Verification
- [ ] Phase 5: Complete
EOF
```

### 3. Start Orchestrator

```bash
# Run full workflow (all 5 phases)
python .workflow/orchestrator.py --start

# Or run individual phases manually
python .workflow/orchestrator.py --phase 1
python .workflow/orchestrator.py --phase 2
# ... etc
```

### 4. Monitor Progress

```bash
# Check workflow state
python .workflow/orchestrator.py --status
# Output: {"phase": "implementation", "phase_num": 3, "status": "running"}

# Watch state in real-time
watch 'python .workflow/orchestrator.py --status'

# Check specific phase output
cat .workflow/phases/01-planning/plan.json

# View coordination log
tail -f .workflow/coordination.log
```

### 5. Review Phase Outputs

```bash
# After Phase 1: Review the plan
cat .workflow/phases/01-planning/plan.json | jq '.tasks'

# After Phase 2: Check reviews
cat .workflow/phases/02-test-design/cursor-feedback.json
cat .workflow/phases/02-test-design/gemini-validation.json

# After Phase 3: Check test results
cat .workflow/phases/03-implementation/test-results.json

# After Phase 4: Check approvals
cat .workflow/phases/04-verification/ready-to-merge.json
```

---

## MANUAL CLI USAGE (If You Prefer)

Run agents individually instead of orchestrator:

```bash
cd /path/to/project

# Phase 1: Claude Planning
claude -p "
Read PRODUCT.md and create detailed plan.
Save to .workflow/phases/01-planning/plan.json
" --append-system-prompt-file=.claude/system.md

# Phase 2: Parallel reviews
cursor-agent -p "Review plan" --rules .cursor/rules &
gemini -p "Validate plan" -e validator-agent &
wait

# Phase 3: Claude Implementation
claude -p "
Read plan and feedback.
Implement with TDD.
Save to .workflow/phases/03-implementation/
" --append-system-prompt-file=.claude/system.md --continue

# Phase 4: Parallel verification
cursor-agent -p "Final review" --rules .cursor/rules &
gemini -p "Final verify" -e validator-agent &
wait

# Check approvals before merging
cat .workflow/phases/04-verification/ready-to-merge.json
```

---

## WHAT EACH AGENT DOES

| Agent | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Role |
|-------|---------|---------|---------|---------|------|
| **Claude** | ✅ Planning | — | ✅ Implementation | — | Planner & Implementer |
| **Cursor** | — | ✅ Review | — | ✅ Final Review | Code Quality Reviewer |
| **Gemini** | — | ✅ Validate | — | ✅ Verify | Architecture Validator |

---

## KEY CONFIGURATIONS

### `.claude/system.md` (Claude's Instructions)
```markdown
You are Claude Code in a multi-agent system.

Your roles:
1. Phase 1: Break PRODUCT.md into testable tasks
2. Phase 3: Implement with tests (TDD approach)

Critical rules:
- Always read PRODUCT.md first
- Incorporate feedback from Cursor and Gemini
- Never commit without test verification
- Document decisions in implementation-log.md

Success: Tests pass + Both agents approved + PRODUCT.md goals achieved
```

### `.cursor/rules` (Cursor's Rules)
```markdown
You are the Code Reviewer.

Your responsibilities:
1. Review code quality, design patterns, security
2. Check test coverage (target: 80%+)
3. Validate architecture decisions

Output format: Always JSON with verdict and score

Coordinate with Gemini - both must approve before merge
```

### `.gemini/GEMINI.md` (Gemini's Identity)
```markdown
You are the Validator Agent.

Your responsibilities:
1. Run tests and verify all pass
2. Check coverage meets targets
3. Validate architecture correctness

Output format: JSON with verdict and findings

You may run in parallel with Cursor
```

### `AGENTS.md` (Shared Definitions)
```markdown
# All Agents Read This

## Roles
- Claude: Planning & Implementation
- Cursor: Code Review
- Gemini: Validation & Verification

## Handoff Protocol
Each agent:
1. Reads previous output: .workflow/phases/{current}/output.json
2. Reads feedback: .workflow/phases/{current}/feedback.json
3. Writes result: .workflow/phases/{current}/result.json

## Parallel Execution
Cursor + Gemini run simultaneously:
- Each reads same input
- Each writes to different file
- Orchestrator merges feedback
- Both must approve before proceeding

## Success Criteria
- All tests passing
- Both agents approved
- No active blockers
- PRODUCT.md goals achieved
```

---

## DIRECTORY STRUCTURE

```
my-project/
├── PRODUCT.md (Your vision - agents read this)
├── AGENTS.md (Shared agent definitions)
├── .rules/ (Shared project rules)
│   ├── base-rules.md
│   └── architecture.md
├── .claude/ (Claude configuration)
│   ├── system.md
│   ├── settings.json
│   ├── rules/
│   └── hooks/
├── .cursor/ (Cursor configuration)
│   └── rules
├── .gemini/ (Gemini configuration)
│   ├── GEMINI.md
│   ├── agents/
│   └── tasks/
├── .workflow/ (ALL workflow artifacts here)
│   ├── orchestrator.py (Main controller)
│   ├── state.json (Current workflow state)
│   ├── coordination.log (All events logged)
│   ├── schemas/ (JSON schemas for validation)
│   ├── logs/ (Detailed logs per phase)
│   └── phases/
│       ├── 01-planning/
│       ├── 02-test-design/
│       ├── 03-implementation/
│       ├── 04-verification/
│       └── 05-completion/
├── src/ (Your code - agents write here)
├── spec/ (Your tests - agents write here)
└── .git/ (Version control - track .workflow/)
```

---

## TROUBLESHOOTING

**Q: Agent lost context between phases?**
A: No, context is file-based. Each agent reads `.workflow/phases/{current}/output.json` from previous phase.

**Q: Getting conflicts between parallel agents?**
A: Each agent writes to separate file (cursor-feedback.json vs gemini-validation.json). No conflicts possible.

**Q: How do agents know which phase they're in?**
A: Read `.workflow/state.json` which specifies phase and task.

**Q: Test results not showing?**
A: Claude must save to `.workflow/phases/03-implementation/test-results.json`. Check claude-output.log for errors.

**Q: Want to run just one phase?**
A: Use orchestrator: `python .workflow/orchestrator.py --phase 2` or run CLI manually.

---

## WHAT TO PROVIDE TO YOUR CODING AGENT

Give your coding agent these 3 files:

1. **multi-agent-guide.md** (Complete architecture documentation)
2. **orchestrator-impl.md** (Full Python implementation with docstrings)
3. **init-multi-agent.sh** (Setup script)

Tell them:
- Expand orchestrator with full phase implementations
- Add error handling and retry logic
- Add comprehensive logging
- Test with real projects (auth service, API, full-stack app)
- Customize prompts per project type
- Add optional MCP servers for rich context

---

## NEXT STEPS FOR IMPLEMENTATION

### For You (Project Owner):
1. Save the 3 files to your coding agent
2. Have agent implement full orchestrator
3. Test with init-multi-agent.sh on sample project
4. Define first feature in PRODUCT.md
5. Run: `python .workflow/orchestrator.py --start`
6. Watch it work through all 5 phases
7. Verify code quality with Cursor + Gemini
8. Merge when both approve

### For Coding Agent:
1. Study the architecture (understand 5-phase flow)
2. Implement orchestrator.py with full phase logic
3. Add subprocess management for parallel execution
4. Create comprehensive error handling
5. Add detailed logging and state management
6. Test each phase independently
7. Verify parallel execution works correctly
8. Add safety checks and validation
9. Document all customization points
10. Create examples for different project types

---

## SUCCESS CRITERIA

Your system works when:
✅ All three CLIs run in same project folder (inherited context)
✅ Phases sequence: Planning → Validation → Implementation → Verification → Completion
✅ Agents communicate via .workflow/ files (no API calls)
✅ Cursor + Gemini run in parallel without conflicts
✅ All tests pass before code review
✅ Both agents must approve before merge
✅ PRODUCT.md drives the entire workflow
✅ Can loop: complete feature → update PRODUCT.md → start new feature
✅ Full traceability in .workflow/coordination.log
✅ Can be version controlled (git tracks .workflow/)

---

**This is production-ready. Give it to a coding agent and you'll have a true multi-agent orchestration system running in your projects!**
