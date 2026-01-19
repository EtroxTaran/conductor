# Gemini Plan Validation Prompt

You are reviewing an implementation plan for architecture and design soundness.

## Context Files
- Read `PRODUCT.md` for the feature specification
- Read `GEMINI.md` for project-specific context
- Read `.workflow/phases/planning/plan.json` for the implementation plan
- Read `.workflow/phases/planning/PLAN.md` for human-readable plan

## Your Task

Review the implementation plan and provide feedback on:

1. **Architecture Soundness**
   - Does the design fit within the existing architecture?
   - Are the component boundaries appropriate?
   - Is the coupling between components reasonable?

2. **Scalability Considerations**
   - Will this design scale with increased load?
   - Are there potential bottlenecks?
   - Is caching strategy appropriate (if applicable)?

3. **Design Patterns**
   - Are appropriate design patterns being used?
   - Are there anti-patterns being introduced?
   - Is the abstraction level appropriate?

4. **System Integration**
   - How does this fit with existing systems?
   - Are API contracts clear and consistent?
   - Are there backwards compatibility concerns?

5. **Performance Implications**
   - Are there potential performance issues?
   - Is the data model efficient?
   - Are there N+1 query risks?

## Output Format

Respond with JSON in this format:

```json
{
  "status": "approved|needs_changes",
  "agent": "gemini",
  "phase": 2,
  "overall_score": 1-10,
  "issues": [
    {
      "severity": "critical|major|minor",
      "category": "architecture|scalability|patterns|integration|performance",
      "description": "Description of the issue",
      "recommendation": "How to fix it",
      "affected_component": "Which part of the plan"
    }
  ],
  "strengths": [
    "What's good about this plan"
  ],
  "alternative_approaches": [
    {
      "approach": "Alternative design option",
      "pros": ["Advantages"],
      "cons": ["Disadvantages"],
      "recommendation": "When to use this instead"
    }
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

- **Approve** if: Architecture is sound, no scalability concerns, fits existing patterns
- **Needs Changes** if: Fundamental design issues, scalability problems, or pattern violations

Think about long-term maintainability and system health, not just immediate functionality.
