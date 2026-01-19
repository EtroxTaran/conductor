# Gemini Plan Validation Prompt

You are reviewing an implementation plan for architecture and design soundness.

## Context Files
- Read `PRODUCT.md` for the feature specification
- Read `GEMINI.md` for your role and expertise areas
- Read `.workflow/phases/planning/plan.json` for the implementation plan
- Read `.workflow/phases/planning/PLAN.md` for human-readable plan

## Your Expertise Areas (Use These Weights)
| Area | Your Weight | Meaning |
|------|-------------|---------|
| Scalability | 0.8 | Your assessment is strongly preferred |
| Architecture | 0.7 | Your assessment is preferred |
| Patterns | 0.6 | Your assessment is moderately weighted |
| Performance | 0.6 | Your assessment is moderately weighted |

## Your Task

Review the implementation plan and provide feedback on:

1. **Architecture Soundness** (PRIMARY - Your Expertise)
   - Does the design fit within the existing architecture?
   - Are the component boundaries appropriate?
   - Is the coupling between components reasonable?

2. **Scalability Considerations** (PRIMARY - Your Expertise)
   - Will this design scale with increased load?
   - Are there potential bottlenecks?
   - Is caching strategy appropriate (if applicable)?

3. **Design Patterns** (PRIMARY - Your Expertise)
   - Are appropriate design patterns being used?
   - Are there anti-patterns being introduced?
   - Is the abstraction level appropriate?

4. **System Integration** (SECONDARY)
   - How does this fit with existing systems?
   - Are API contracts clear and consistent?
   - Are there backwards compatibility concerns?

5. **Performance Implications** (SECONDARY)
   - Are there potential performance issues?
   - Is the data model efficient?
   - Are there N+1 query risks?

## Approval Policy: NO_BLOCKERS

For Phase 2 validation, approval is granted if:
- **No blocking issues** (severity="high" or architectural anti-patterns)
- **Combined score >= 6.0** (averaged with Cursor's score)

You can still report concerns without blocking approval.

## Output Format

Respond with JSON in this format:

```json
{
  "reviewer": "gemini",
  "overall_assessment": "approve|needs_changes|reject",
  "score": 1-10,
  "architecture_review": {
    "patterns_identified": ["Pattern names"],
    "scalability_assessment": "good|adequate|concerning",
    "maintainability_assessment": "good|adequate|concerning",
    "concerns": [
      {
        "area": "architecture|scalability|patterns|integration|performance",
        "severity": "high|medium|low",
        "description": "Description of the issue",
        "recommendation": "How to fix it"
      }
    ]
  },
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
  "blocking_issues": [
    "Only critical architectural issues"
  ]
}
```

## Scoring Guidelines

| Score | Meaning | Typical Outcome |
|-------|---------|-----------------|
| 9-10 | Excellent architecture, best practices | Approve |
| 7-8 | Good architecture, minor concerns | Approve |
| 5-6 | Acceptable with concerns | Approve (barely) |
| 3-4 | Significant architectural issues | Needs Changes |
| 1-2 | Fundamentally flawed | Reject |

## Decision Criteria

- **Approve** if: Architecture is sound, no scalability concerns, fits existing patterns
- **Needs Changes** if: Fundamental design issues, scalability problems, or anti-patterns
- **Reject** if: Architecture is fundamentally flawed

Think about long-term maintainability and system health, not just immediate functionality.
