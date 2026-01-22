---
description: Run Phase 2 validation with Cursor and Gemini
allowed-tools: ["Bash", "Read", "Write", "Edit"]
---

# Plan Validation (Phase 2)

Run Cursor and Gemini in parallel to validate the implementation plan.

## Prerequisites

- Phase 1 (Planning) must be complete
- `.workflow/phases/planning/plan.json` must exist

## Instructions

### 1. Prepare

```bash
mkdir -p .workflow/phases/validation
```

### 2. Read Plan

```
Read: .workflow/phases/planning/plan.json
```

### 3. Run Agents in Parallel

Execute BOTH commands simultaneously:

**Cursor (Security Focus)**:
```bash
cursor-agent --print --output-format json "
# Plan Validation - Security & Code Quality

Review the plan at .workflow/phases/planning/plan.json for:
1. Security vulnerabilities in proposed changes
2. Code quality concerns
3. Testing coverage adequacy
4. OWASP Top 10 risks

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
gemini --yolo "
# Plan Validation - Architecture & Scalability

Review the plan at .workflow/phases/planning/plan.json for:
1. Architecture patterns and design
2. Scalability considerations
3. Technical debt risks
4. Maintainability

Return JSON in code block:
\`\`\`json
{
  \"agent\": \"gemini\",
  \"approved\": true|false,
  \"score\": 1-10,
  \"assessment\": \"summary\",
  \"concerns\": [{\"area\": \"\", \"severity\": \"high|medium|low\", \"description\": \"\"}],
  \"blocking_issues\": []
}
\`\`\`
" > .workflow/phases/validation/gemini-feedback.json
```

### 4. Evaluate Results

Read both feedback files and check:

| Criterion | Requirement |
|-----------|-------------|
| Cursor Score | >= 6.0 |
| Gemini Score | >= 6.0 |
| Blocking Issues | None |

### 5. Handle Conflicts

If agents disagree, use `/resolve-conflict`:
- Security issues: Cursor weight 0.8
- Architecture issues: Gemini weight 0.7

### 6. Update State

**If Approved**:
```json
{
  "current_phase": 3,
  "phase_status": { "validation": "completed" },
  "validation_feedback": { "cursor": {...}, "gemini": {...} }
}
```

**If Not Approved**:
Return to Phase 1 with feedback to address concerns.

## Approval Thresholds

- Combined score >= 6.0
- No blocking issues from either agent
- Use `/resolve-conflict` for disagreements

## Related Skills

- `/plan-feature` - Previous phase
- `/call-cursor` - Cursor details
- `/call-gemini` - Gemini details
- `/resolve-conflict` - Conflict resolution
