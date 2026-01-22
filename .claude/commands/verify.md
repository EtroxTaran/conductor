---
description: Run Phase 4 verification with Cursor and Gemini
allowed-tools: ["Bash", "Read", "Write", "Edit"]
---

# Code Verification (Phase 4)

Run Cursor and Gemini in parallel to verify the implementation.

## Prerequisites

- Phase 3 (Implementation) must be complete
- All tasks marked as "completed"
- Tests passing

## Instructions

### 1. Prepare

```bash
mkdir -p .workflow/phases/verification
```

### 2. Gather Implementation Info

Read task completion records and list changed files.

### 3. Run Agents in Parallel

Execute BOTH commands simultaneously:

**Cursor (Security Audit)**:
```bash
cursor-agent --print --output-format json "
# Code Review - Security Audit

Review the implemented code for:
1. OWASP Top 10 vulnerabilities
2. Injection flaws (SQL, XSS, command)
3. Authentication/authorization issues
4. Sensitive data exposure
5. Input validation

Return JSON:
{
  \"agent\": \"cursor\",
  \"approved\": true|false,
  \"score\": 1-10,
  \"assessment\": \"summary\",
  \"security_issues\": [{\"severity\": \"critical|high|medium|low\", \"file\": \"\", \"line\": 0, \"description\": \"\", \"fix\": \"\"}],
  \"blocking_issues\": []
}
" > .workflow/phases/verification/cursor-review.json
```

**Gemini (Architecture Review)**:
```bash
gemini --yolo "
# Code Review - Architecture Compliance

Review the implemented code for:
1. Architecture compliance with plan
2. Design pattern correctness
3. Modularity and separation of concerns
4. Maintainability

Return JSON in code block:
\`\`\`json
{
  \"agent\": \"gemini\",
  \"approved\": true|false,
  \"score\": 1-10,
  \"assessment\": \"summary\",
  \"architecture_issues\": [{\"file\": \"\", \"concern\": \"\", \"severity\": \"high|medium|low\"}],
  \"blocking_issues\": []
}
\`\`\`
" > .workflow/phases/verification/gemini-review.json
```

### 4. Evaluate Results

**BOTH agents must approve** (Phase 4 is stricter):

| Criterion | Requirement |
|-----------|-------------|
| Cursor Score | >= 7.0 |
| Gemini Score | >= 7.0 |
| Cursor Approved | **Yes** |
| Gemini Approved | **Yes** |
| Security Issues | None high/critical |
| Blocking Issues | None |

### 5. Handle Non-Approval

**Security Issues**: Return to Phase 3, create fix tasks.
**Architecture Issues**: Evaluate severity, may need refactoring.

### 6. Update State

**If Approved**:
```json
{
  "current_phase": 5,
  "phase_status": { "verification": "completed" },
  "verification_feedback": { "cursor": {...}, "gemini": {...} }
}
```

**If Not Approved**:
```json
{
  "current_phase": 3,
  "phase_status": { "verification": "needs_fixes" },
  "fix_tasks": [...]
}
```

## Approval Thresholds

- BOTH agents must approve
- Scores >= 7.0 each
- No blocking issues
- No high/critical security vulnerabilities

## Related Skills

- `/implement-task` - Previous phase
- `/call-cursor` - Cursor details
- `/call-gemini` - Gemini details
- `/resolve-conflict` - Conflict resolution
