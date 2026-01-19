---
description: Start or resume the 5-phase multi-agent workflow
allowed-tools: ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "Task", "TodoWrite"]
---

# Multi-Agent Workflow Orchestration

Start or resume the 5-phase workflow to implement the feature described in PRODUCT.md.

## Context Loading

Read these files in order:
1. `AGENTS.md` - Complete workflow rules
2. `PRODUCT.md` - Feature specification
3. `.workflow/state.json` - Current workflow state

## Workflow Phases

| Phase | Name | Lead | Description |
|-------|------|------|-------------|
| 1 | Planning | Claude | Create detailed plan from PRODUCT.md |
| 2 | Validation | Cursor + Gemini | Parallel review of plan |
| 3 | Implementation | Claude | TDD-first implementation |
| 4 | Verification | Cursor + Gemini | Parallel code review |
| 5 | Completion | Claude | Final documentation |

## Instructions

### If No Workflow Exists

1. Read `PRODUCT.md` thoroughly
2. Create `plan.json` with:
   - Feature overview
   - File changes required
   - Implementation steps
   - Test strategy
3. Save to `.workflow/phases/planning/plan.json`
4. Update `.workflow/state.json` to phase 2
5. Proceed to validation

### If Workflow Exists

1. Read `.workflow/state.json` to determine current phase
2. Resume from the current phase
3. If blocked, read feedback files and address issues

### Validation (Phase 2)

Run both agents in parallel:

```bash
# Create validation prompts first
bash scripts/call-cursor.sh .workflow/phases/validation/cursor-prompt.md .workflow/phases/validation/cursor-feedback.json

bash scripts/call-gemini.sh .workflow/phases/validation/gemini-prompt.md .workflow/phases/validation/gemini-feedback.json
```

Evaluate approval using the approval engine policy.

### Implementation (Phase 3)

Follow TDD:
1. Write failing tests first
2. Implement code to pass tests
3. Refactor as needed
4. Run test suite

### Verification (Phase 4)

Run both agents to verify implementation:

```bash
bash scripts/call-cursor.sh .workflow/phases/verification/cursor-prompt.md .workflow/phases/verification/cursor-review.json

bash scripts/call-gemini.sh .workflow/phases/verification/gemini-prompt.md .workflow/phases/verification/gemini-review.json
```

Both must approve with score >= 7.0 for ALL_MUST_APPROVE policy.

## Context Drift

The workflow tracks context files with checksums. If context drift is detected:
- Warning is logged but workflow continues (default)
- Use `/phase-status` to check drift details
- Re-sync context if needed

## Output

Update `.workflow/state.json` after each phase transition.
Save all artifacts to the appropriate phase directory.
