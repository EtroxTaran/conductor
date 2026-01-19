---
description: Resolve conflicts between Cursor and Gemini feedback
allowed-tools: ["Read", "Write"]
---

# Conflict Resolution

Handle disagreements between Cursor and Gemini using the weighted expertise policy.

## Expertise Weights

| Area | Cursor Weight | Gemini Weight | Preferred |
|------|---------------|---------------|-----------|
| Security | 0.8 | 0.2 | Cursor |
| Architecture | 0.3 | 0.7 | Gemini |
| Code Quality | 0.7 | 0.3 | Cursor |
| Scalability | 0.2 | 0.8 | Gemini |
| Maintainability | 0.6 | 0.4 | Cursor |
| Testing | 0.7 | 0.3 | Cursor |
| Performance | 0.4 | 0.6 | Gemini |
| Patterns | 0.4 | 0.6 | Gemini |

## Conflict Types

### 1. Approval Mismatch
One agent approves, the other rejects.

**Resolution**:
- In Phase 2 (Validation): Use NO_BLOCKERS policy - approve if no high-severity issues
- In Phase 4 (Verification): Use CONSERVATIVE - take rejection

### 2. Severity Disagreement
Agents assign different severity to same issue.

**Resolution**:
- Use expertise weights for the issue area
- Higher weighted agent's severity wins
- Example: Security issue -> Cursor's severity

### 3. Score Divergence
Scores differ by >= 3 points.

**Resolution**:
- Calculate weighted average based on expertise
- Consider the areas of concern

## Resolution Strategies

### WEIGHTED (Default for Phase 2)
Use expertise weights to determine winner.

### CONSERVATIVE (Default for Phase 4)
Take the more cautious position:
- For approval: take rejection
- For severity: take higher severity
- For scores: take lower score

### UNANIMOUS
Require both to agree. Escalate if no agreement.

### ESCALATE
Always require human decision.

### DEFER_TO_LEAD
Claude as lead orchestrator makes the decision.

## Instructions

1. Read the conflicting feedback files
2. Identify conflict type
3. Determine the applicable area (security, architecture, etc.)
4. Apply the appropriate resolution strategy
5. Document the resolution in `.workflow/phases/{phase}/conflict-resolution.json`:

```json
{
  "conflicts": [
    {
      "type": "approval_mismatch",
      "area": "overall_approval",
      "cursor_position": "approve",
      "gemini_position": "reject",
      "resolution": {
        "strategy": "weighted",
        "winner": "gemini",
        "reason": "Architecture area: Gemini weight 0.7"
      }
    }
  ],
  "overall_recommendation": "revise|proceed|escalate"
}
```

## When to Escalate

Escalate to human decision when:
- UNANIMOUS strategy is used and agents disagree
- Equal weights result in tie
- Multiple high-severity conflicts exist
- Resolution is unclear

Output message: "Conflict requires human decision. Review the feedback and provide direction."
