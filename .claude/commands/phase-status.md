---
description: Show current workflow status and progress
allowed-tools: ["Read", "Glob"]
---

# Workflow Status Check

Display the current state of the multi-agent workflow.

## Instructions

1. Read `.workflow/state.json`
2. Display status in this format:

```
## Workflow Status

| Field | Value |
|-------|-------|
| Project | {project_name} |
| Current Phase | {current_phase}/5 |
| Iteration | {iteration_count} |

## Phase Status

| Phase | Name | Status | Attempts |
|-------|------|--------|----------|
| 1 | Planning | {status} | {attempts}/3 |
| 2 | Validation | {status} | {attempts}/3 |
| 3 | Implementation | {status} | {attempts}/3 |
| 4 | Verification | {status} | {attempts}/3 |
| 5 | Completion | {status} | {attempts}/3 |
```

3. If context tracking is enabled:
   - Check for drift using stored checksums
   - Report any changed files

4. Report any blockers or errors for the current phase

## Context Drift Check

If `.workflow/state.json` contains a `context` field:
- Compare stored checksums to current files
- Report changed files: AGENTS.md, PRODUCT.md, etc.

## Recent Activity

Read and summarize recent phase outputs:
- `.workflow/phases/{current_phase}/` for phase artifacts
- Any approval or feedback files

## Output Format

Keep output concise and actionable. Highlight:
- Current phase and what to do next
- Any blocking issues
- Approval status if in validation/verification
