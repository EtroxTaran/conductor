---
description: Run Phase 4 verification on implemented code
allowed-tools: ["Bash", "Read", "Write", "Edit"]
---

# Implementation Verification (Phase 4)

Run Cursor and Gemini to verify the implemented code.

## Prerequisites

- Phase 3 (Implementation) must be complete
- Implementation results must exist
- Tests must be passing

## Instructions

### 1. Gather Context

Read these files:
- `.workflow/phases/implementation/implementation-results.json`
- `.workflow/phases/planning/plan.json`
- Get list of files changed/created

### 2. Create Verification Prompts

**Cursor Review Prompt** (`.workflow/phases/verification/cursor-prompt.md`):
```markdown
# Code Review Request

Review the following implementation for bugs, security, and code quality.

## Files Changed
{files_list}

## Test Results
{test_summary}

## Your Focus
- Bug detection
- Security vulnerabilities
- Code style and best practices
- Test coverage

## Output Format
Return JSON with:
{
  "reviewer": "cursor",
  "approved": true|false,
  "overall_code_quality": 1-10,
  "files_reviewed": [
    {"file": "", "issues": [{"type": "", "severity": "error|warning", "description": ""}]}
  ],
  "blocking_issues": []
}
```

**Gemini Review Prompt** (`.workflow/phases/verification/gemini-prompt.md`):
```markdown
# Architecture Review Request

Review the implementation against the original plan.

## Plan
{plan_json}

## Files Changed
{files_list}

## Your Focus
- Plan conformance
- Architecture integrity
- Modularity and coupling
- Technical debt

## Output Format
Return JSON with:
{
  "reviewer": "gemini",
  "approved": true|false,
  "architecture_assessment": {
    "modularity_score": 1-10,
    "conforms_to_plan": true|false
  },
  "blocking_issues": [],
  "technical_debt": {"items": []}
}
```

### 3. Run Reviewers in Parallel

```bash
bash scripts/call-cursor.sh .workflow/phases/verification/cursor-prompt.md .workflow/phases/verification/cursor-review.json &
bash scripts/call-gemini.sh .workflow/phases/verification/gemini-prompt.md .workflow/phases/verification/gemini-review.json &
wait
```

### 4. Evaluate Results

**ALL_MUST_APPROVE Policy (Phase 4 Default)**:
- BOTH agents must approve
- Minimum score: 7.0
- No blocking issues

### 5. Handle Conflicts

Use CONSERVATIVE strategy in Phase 4:
- For approval mismatch: take the rejection
- For severity disagreement: take the higher severity
- This ensures quality before merge

### 6. Generate Merge Status

Create `.workflow/phases/verification/ready-to-merge.json`:
```json
{
  "approved": true|false,
  "cursor_approved": true|false,
  "gemini_approved": true|false,
  "combined_score": 8.5,
  "blocking_issues": [],
  "timestamp": "ISO-8601"
}
```

### 7. Update State

If approved:
- Update state to phase 5
- Proceed to completion

If not approved:
- Log blocking issues
- Return to phase 3 with feedback
- Increment iteration count
