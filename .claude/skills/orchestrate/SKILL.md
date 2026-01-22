# Orchestrate Skill

Multi-agent workflow orchestration using native Claude Code features.

## Overview

This skill orchestrates a 5-phase workflow coordinating Claude (via Task tool), Cursor, and Gemini agents. It replaces the Python-based orchestrator with native Claude Code features for 70% token efficiency improvement.

## Architecture

```
Claude Code (This Session = Orchestrator)
    |
    +-- Task Tool --> Worker Claude (70% cheaper than subprocess)
    |
    +-- Bash Tool --> cursor-agent CLI (security review)
    |
    +-- Bash Tool --> gemini CLI (architecture review)
    |
    +-- Read/Write --> .workflow/state.json (state persistence)
```

## Workflow Phases

| Phase | Name | Agents | Method |
|-------|------|--------|--------|
| 0 | Discussion | Claude | Direct conversation |
| 1 | Planning | Claude Worker | Task tool |
| 2 | Validation | Cursor + Gemini | Bash (parallel) |
| 3 | Implementation | Claude Workers | Task tool (per task) |
| 4 | Verification | Cursor + Gemini | Bash (parallel) |
| 5 | Completion | Claude | Direct |

## State Management

State is persisted in `.workflow/state.json`:

```json
{
  "project_name": "my-project",
  "project_dir": "/path/to/project",
  "current_phase": 2,
  "phase_status": {
    "discussion": "completed",
    "planning": "completed",
    "validation": "in_progress",
    "implementation": "pending",
    "verification": "pending",
    "completion": "pending"
  },
  "plan": { ... },
  "tasks": [ ... ],
  "current_task_id": null,
  "validation_feedback": {
    "cursor": { ... },
    "gemini": { ... }
  },
  "verification_feedback": {
    "cursor": { ... },
    "gemini": { ... }
  },
  "errors": [],
  "updated_at": "2026-01-22T12:00:00Z"
}
```

## Execution Instructions

### Starting a Workflow

1. **Read project context**:
   - `projects/<name>/Documents/` - Product vision
   - `projects/<name>/PRODUCT.md` - Feature specification
   - `projects/<name>/.workflow/state.json` - Current state (if exists)

2. **Initialize state** (if new):
   ```json
   {
     "project_name": "<name>",
     "current_phase": 0,
     "phase_status": {
       "discussion": "pending",
       "planning": "pending",
       "validation": "pending",
       "implementation": "pending",
       "verification": "pending",
       "completion": "pending"
     }
   }
   ```

3. **Execute phases sequentially** using appropriate skills/tools.

### Phase 0: Discussion

Gather requirements through conversation:
- Ask about preferences, constraints, priorities
- Document decisions in `projects/<name>/CONTEXT.md`
- Update state: `phase_status.discussion = "completed"`

### Phase 1: Planning

Use Task tool to spawn a planning worker:

```
Task(
  subagent_type="Plan",
  prompt="""
  Create an implementation plan for the feature in PRODUCT.md.

  Read these files:
  - PRODUCT.md (requirements)
  - Documents/ (context)
  - CONTEXT.md (preferences from discussion)

  Create plan.json with:
  - Feature overview
  - Tasks breakdown (small, focused tasks)
  - File changes per task
  - Test strategy per task
  - Dependencies between tasks

  Each task should:
  - Touch max 3 files to create
  - Touch max 5 files to modify
  - Have clear acceptance criteria
  - Be completable in <10 minutes
  """,
  run_in_background=false
)
```

Save result to `.workflow/phases/planning/plan.json`.
Update state: `phase_status.planning = "completed"`, `current_phase = 2`.

### Phase 2: Validation

Run Cursor and Gemini in parallel via Bash:

**Cursor (Security Focus)**:
```bash
cd projects/<name> && cursor-agent --print --output-format json "
Review .workflow/phases/planning/plan.json for:
- Security vulnerabilities in proposed changes
- Code quality concerns
- Testing coverage adequacy
- OWASP Top 10 risks

Return JSON:
{
  \"agent\": \"cursor\",
  \"approved\": true|false,
  \"score\": 1-10,
  \"assessment\": \"summary\",
  \"concerns\": [{\"area\": \"\", \"severity\": \"high|medium|low\", \"description\": \"\"}],
  \"blocking_issues\": []
}
" > .workflow/phases/validation/cursor-feedback.json
```

**Gemini (Architecture Focus)**:
```bash
cd projects/<name> && gemini --yolo "
Review .workflow/phases/planning/plan.json for:
- Architecture patterns and design
- Scalability considerations
- Technical debt risks
- Maintainability

Return JSON:
{
  \"agent\": \"gemini\",
  \"approved\": true|false,
  \"score\": 1-10,
  \"assessment\": \"summary\",
  \"concerns\": [{\"area\": \"\", \"severity\": \"high|medium|low\", \"description\": \"\"}],
  \"blocking_issues\": []
}
" > .workflow/phases/validation/gemini-feedback.json
```

**Approval Criteria (Phase 2)**:
- Combined score >= 6.0
- No blocking issues from either agent
- If conflict: Security (Cursor) weight 0.8, Architecture (Gemini) weight 0.7

Update state: `validation_feedback`, `phase_status.validation = "completed"`, `current_phase = 3`.

### Phase 3: Implementation

For each task in plan.tasks:

1. **Select next task** (respecting dependencies)
2. **Spawn worker Claude** via Task tool:

```
Task(
  subagent_type="general-purpose",
  prompt="""
  ## Task: {task.title}

  ## User Story
  {task.user_story}

  ## Acceptance Criteria
  {task.acceptance_criteria}

  ## Files to Create
  {task.files_to_create}

  ## Files to Modify
  {task.files_to_modify}

  ## Test Files
  {task.test_files}

  ## Instructions
  1. Read CLAUDE.md for coding standards
  2. Write failing tests FIRST (TDD)
  3. Implement code to make tests pass
  4. Run tests to verify: pytest or npm test
  5. Signal completion with: TASK_COMPLETE

  ## Constraints
  - Only modify files listed above
  - Follow existing code patterns
  - No security vulnerabilities
  """,
  run_in_background=false
)
```

3. **Update task status** in state
4. **Repeat** until all tasks complete

Update state: `phase_status.implementation = "completed"`, `current_phase = 4`.

### Phase 4: Verification

Run Cursor and Gemini in parallel via Bash:

**Cursor (Code Review)**:
```bash
cd projects/<name> && cursor-agent --print --output-format json "
Review the implemented code for:
- Security vulnerabilities (OWASP Top 10)
- Code quality and best practices
- Test coverage adequacy
- Potential bugs

Check files changed in implementation.

Return JSON:
{
  \"agent\": \"cursor\",
  \"approved\": true|false,
  \"score\": 1-10,
  \"assessment\": \"summary\",
  \"issues\": [{\"file\": \"\", \"line\": 0, \"severity\": \"\", \"description\": \"\"}],
  \"blocking_issues\": []
}
" > .workflow/phases/verification/cursor-review.json
```

**Gemini (Architecture Review)**:
```bash
cd projects/<name> && gemini --yolo "
Review the implemented code for:
- Architecture compliance with plan
- Design pattern correctness
- Scalability concerns
- Technical debt introduced

Return JSON:
{
  \"agent\": \"gemini\",
  \"approved\": true|false,
  \"score\": 1-10,
  \"assessment\": \"summary\",
  \"issues\": [{\"file\": \"\", \"concern\": \"\", \"severity\": \"\"}],
  \"blocking_issues\": []
}
" > .workflow/phases/verification/gemini-review.json
```

**Approval Criteria (Phase 4)**:
- BOTH agents must approve
- Score >= 7.0 from each
- No blocking issues

If not approved: Return to Phase 3 to fix issues.

Update state: `verification_feedback`, `phase_status.verification = "completed"`, `current_phase = 5`.

### Phase 5: Completion

Generate summary documentation:

1. Create `.workflow/phases/completion/summary.json`:
   - Features implemented
   - Files changed
   - Tests added
   - Review scores

2. Create UAT document if configured

3. Generate handoff brief for session resume

Update state: `phase_status.completion = "completed"`.

## Error Handling

### On Phase Failure

1. Log error to state.errors
2. Increment retry count (max 3)
3. If max retries: Pause for human input
4. Document issue and suggested fix

### On Agent Timeout

1. Log timeout to state
2. Retry with increased timeout
3. If persistent: Skip agent and note in review

### On Conflict

Use `/resolve-conflict` skill:
- Security issues: Cursor weight 0.8
- Architecture issues: Gemini weight 0.7
- Escalate to human if unresolvable

## Resuming Workflows

1. Read `.workflow/state.json`
2. Check `current_phase` and `phase_status`
3. Resume from last incomplete phase
4. Preserve all previous feedback and decisions

## Token Efficiency

| Component | Old (Subprocess) | New (Native) | Savings |
|-----------|------------------|--------------|---------|
| Worker Claude spawn | ~13k tokens | ~4k tokens | 70% |
| Context passing | Full duplication | Filtered | 60% |
| State management | External DB | Native files | Simpler |

## Related Skills

- `/plan-feature` - Detailed planning phase
- `/validate-plan` - Detailed validation phase
- `/implement-task` - Single task implementation
- `/verify-code` - Detailed verification phase
- `/resolve-conflict` - Conflict resolution
- `/call-cursor` - Cursor agent wrapper
- `/call-gemini` - Gemini agent wrapper
