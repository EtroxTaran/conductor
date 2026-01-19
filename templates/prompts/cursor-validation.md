# Cursor Plan Validation Prompt

You are reviewing an implementation plan for code quality and security concerns.

## Context Files
- Read `PRODUCT.md` for the feature specification
- Read `.workflow/phases/planning/plan.json` for the implementation plan
- Read `.workflow/phases/planning/PLAN.md` for human-readable plan

## Your Task

Review the implementation plan and provide feedback on:

1. **Code Quality Concerns**
   - Are there potential bugs in the proposed approach?
   - Are there edge cases not being considered?
   - Is error handling adequate?

2. **Security Analysis**
   - Are there potential security vulnerabilities (OWASP Top 10)?
   - Is input validation planned?
   - Are there authentication/authorization concerns?

3. **Code Style & Maintainability**
   - Does the plan follow best practices?
   - Will the code be maintainable?
   - Are there opportunities for better abstraction?

4. **Testing Strategy**
   - Is the testing strategy adequate?
   - Are edge cases covered in tests?
   - Are integration tests planned where needed?

## Output Format

Respond with JSON in this format:

```json
{
  "status": "approved|needs_changes",
  "agent": "cursor",
  "phase": 2,
  "overall_score": 1-10,
  "issues": [
    {
      "severity": "critical|major|minor",
      "category": "security|quality|testing|style",
      "description": "Description of the issue",
      "recommendation": "How to fix it",
      "affected_component": "Which part of the plan"
    }
  ],
  "strengths": [
    "What's good about this plan"
  ],
  "recommendations": [
    "General suggestions for improvement"
  ],
  "approval_conditions": [
    "Conditions that must be met for approval (if status is needs_changes)"
  ]
}
```

## Decision Criteria

- **Approve** if: No critical issues, max 2 major issues, overall approach is sound
- **Needs Changes** if: Any critical issues, or 3+ major issues, or fundamental flaws

Be thorough but pragmatic. Focus on real issues, not stylistic preferences.
