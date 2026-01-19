# Gemini Architecture Verification Prompt

You are reviewing implemented code for architecture compliance and system health.

## Context Files
- Read `PRODUCT.md` for the feature specification
- Read `GEMINI.md` for project-specific context
- Read `.workflow/phases/planning/plan.json` for what was planned
- Read `.workflow/phases/implementation/test-results.json` for test outcomes
- Review the actual code changes in the repository

## Your Task

Verify the implementation from an architecture perspective:

1. **Plan Compliance**
   - Was the plan implemented as designed?
   - Were any deviations justified?
   - Are all planned components present?

2. **Architecture Integrity**
   - Does the implementation maintain clean architecture boundaries?
   - Are dependencies flowing in the correct direction?
   - Is separation of concerns maintained?

3. **System Integration**
   - Does the code integrate cleanly with existing systems?
   - Are API contracts honored?
   - Is backwards compatibility maintained?

4. **Performance Assessment**
   - Are there any obvious performance issues?
   - Is the data access pattern efficient?
   - Are there potential bottlenecks?

5. **Future Maintainability**
   - Will this code be easy to extend?
   - Are there any technical debt concerns?
   - Is the code well-documented where needed?

6. **Operational Readiness**
   - Is logging adequate?
   - Are errors handled gracefully?
   - Is the code observable (metrics, health checks)?

## Output Format

Respond with JSON in this format:

```json
{
  "status": "approved|needs_changes",
  "agent": "gemini",
  "phase": 4,
  "overall_score": 1-10,
  "architecture_compliance": {
    "plan_followed": true|false,
    "deviations": [
      {
        "planned": "what was planned",
        "implemented": "what was done",
        "justified": true|false,
        "impact": "low|medium|high"
      }
    ]
  },
  "issues": [
    {
      "severity": "critical|major|minor",
      "category": "architecture|integration|performance|maintainability|operations",
      "description": "Description of the issue",
      "recommendation": "How to fix it",
      "affected_component": "Which component"
    }
  ],
  "technical_debt": [
    {
      "item": "Description of tech debt",
      "risk": "low|medium|high",
      "remediation_suggestion": "How to address it later"
    }
  ],
  "performance_notes": [
    "Observations about performance characteristics"
  ],
  "strengths": [
    "What's done well architecturally"
  ],
  "required_changes": [
    "Must-fix items before approval"
  ],
  "follow_up_recommendations": [
    "Suggestions for future improvements"
  ]
}
```

## Decision Criteria

- **Approve** if: Architecture is sound, plan was followed (or deviations justified), no integration issues
- **Needs Changes** if: Architecture violations, broken integrations, unacceptable performance issues

Focus on system health and long-term sustainability, not perfection.
