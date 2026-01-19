---
description: Run Phase 2 validation with Cursor and Gemini
allowed-tools: ["Bash", "Read", "Write", "Edit"]
---

# Plan Validation (Phase 2)

Run Cursor and Gemini to validate the current plan.

## Prerequisites

- Phase 1 (Planning) must be complete
- `.workflow/phases/planning/plan.json` must exist

## Instructions

### 1. Read the Plan

Read `.workflow/phases/planning/plan.json`

### 2. Create Validation Prompts

Create prompts for each agent:

**Cursor Prompt** (`.workflow/phases/validation/cursor-prompt.md`):
```markdown
# Plan Validation Request

Review the following implementation plan for code quality, security, and maintainability.

## Plan
{plan_json}

## Your Focus
- Security vulnerabilities
- Code quality issues
- Testing coverage
- Maintainability concerns

## Output Format
Return JSON with:
{
  "reviewer": "cursor",
  "overall_assessment": "approve|needs_changes|reject",
  "score": 1-10,
  "concerns": [{"area": "", "severity": "high|medium|low", "description": ""}],
  "strengths": [],
  "blocking_issues": []
}
```

**Gemini Prompt** (`.workflow/phases/validation/gemini-prompt.md`):
```markdown
# Architecture Validation Request

Review the following implementation plan for architecture and scalability.

## Plan
{plan_json}

## Your Focus
- Architecture patterns
- Scalability concerns
- Design principles
- Technical debt risks

## Output Format
Return JSON with:
{
  "reviewer": "gemini",
  "overall_assessment": "approve|needs_changes|reject",
  "score": 1-10,
  "architecture_review": {"concerns": [], "patterns_identified": []},
  "blocking_issues": []
}
```

### 3. Run Agents in Parallel

```bash
bash scripts/call-cursor.sh .workflow/phases/validation/cursor-prompt.md .workflow/phases/validation/cursor-feedback.json &
bash scripts/call-gemini.sh .workflow/phases/validation/gemini-prompt.md .workflow/phases/validation/gemini-feedback.json &
wait
```

### 4. Evaluate Results

Read both feedback files and evaluate using the approval policy:

**NO_BLOCKERS Policy (Phase 2 Default)**:
- Approve if no blocking issues AND combined score >= 6.0
- Concerns are logged but don't block

### 5. Generate Consolidated Feedback

Create `.workflow/phases/validation/consolidated-feedback.json` with:
- Both feedback summaries
- Overall recommendation: proceed | revise_plan | review_concerns
- All blocking issues

### 6. Handle Conflicts

If agents disagree (approval mismatch):
- Use weighted resolution: Security -> Cursor (0.8), Architecture -> Gemini (0.7)
- Log resolution in output

### 7. Update State

If approved:
- Update `.workflow/state.json` to phase 3
- Continue to implementation

If not approved:
- Increment iteration_count
- Return to phase 1 with feedback
