"""Conflict Resolver for 4-Eyes Verification Protocol.

Resolves disagreements between reviewers (Cursor/Security vs Gemini/Architecture)
using weighted authority based on domain expertise.
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ReviewResult:
    """Standardized review result."""
    approved: bool
    score: float
    blocking_issues: List[str]
    agent_id: str

@dataclass
class ResolutionResult:
    """Result of conflict resolution."""
    approved: bool
    final_score: float
    decision_reason: str
    blocking_issues: List[Dict[str, Any]]
    action: str  # "approve", "reject", "escalate"

class ConflictResolver:
    """Resolves verification conflicts using weighted domain expertise."""

    # Weights for overall score calculation
    # Reflects the general reliability/specialization of each agent
    DEFAULT_WEIGHTS = {
        "cursor": 0.6,  # Stronger on code/security/implementation details
        "gemini": 0.4,  # Stronger on high-level architecture/patterns
    }

    # Domain-specific authority override weights
    # If an issue is flagged in this domain, that agent's voice carries this weight
    DOMAIN_AUTHORITY = {
        "security": "cursor",      # Cursor is the security authority
        "vulnerability": "cursor",
        "injection": "cursor",     # SQL/Command injection
        "architecture": "gemini",  # Gemini is the architecture authority
        "pattern": "gemini",
        "structure": "gemini",
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS

    def resolve(
        self, 
        cursor_review: Dict[str, Any], 
        gemini_review: Dict[str, Any]
    ) -> ResolutionResult:
        """Resolve verification results from multiple agents.

        Args:
            cursor_review: Feedback dict from Cursor (A07)
            gemini_review: Feedback dict from Gemini (A08)

        Returns:
            ResolutionResult
        """
        # Parse inputs into standardized objects
        r1 = self._parse_review(cursor_review, "cursor")
        r2 = self._parse_review(gemini_review, "gemini")

        # 1. Collect all blocking issues
        all_blockers = []
        for b in r1.blocking_issues:
            all_blockers.append({"agent": "cursor", "issue": b})
        for b in r2.blocking_issues:
            all_blockers.append({"agent": "gemini", "issue": b})

        # 2. Check for Authority Vetos (Immediate Rejection)
        # If an authority flags a blocker in their domain, we reject immediately
        authority_veto = self._check_authority_veto(all_blockers)
        if authority_veto:
            return ResolutionResult(
                approved=False,
                final_score=0.0,
                decision_reason=f"Authority Veto: {authority_veto}",
                blocking_issues=all_blockers,
                action="reject"
            )

        # 3. Calculate Weighted Score
        # Normalize scores to 0-10 range if needed
        s1 = r1.score
        s2 = r2.score
        
        w1 = self.weights.get("cursor", 0.5)
        w2 = self.weights.get("gemini", 0.5)
        
        # Re-normalize weights to sum to 1.0
        total_w = w1 + w2
        w1 = w1 / total_w
        w2 = w2 / total_w

        weighted_score = (s1 * w1) + (s2 * w2)

        # 4. Determine Outcome
        MIN_SCORE = 7.0
        
        # If blockers exist, reject regardless of score
        if all_blockers:
            return ResolutionResult(
                approved=False,
                final_score=weighted_score,
                decision_reason=f"Rejected due to {len(all_blockers)} blocking issues",
                blocking_issues=all_blockers,
                action="reject"
            )

        # If substantial disagreement (variance > 3.0), escalate
        # We do this before checking the score because a high variance means the score is unreliable
        if abs(s1 - s2) > 3.0:
            return ResolutionResult(
                approved=False,
                final_score=weighted_score,
                decision_reason=f"High disagreement (Diff: {abs(s1-s2):.1f}). Cursor={s1}, Gemini={s2}",
                blocking_issues=[],
                action="escalate"
            )

        # If score is too low, reject
        if weighted_score < MIN_SCORE:
            return ResolutionResult(
                approved=False,
                final_score=weighted_score,
                decision_reason=f"Score {weighted_score:.1f} below threshold {MIN_SCORE}",
                blocking_issues=[],
                action="reject"
            )

        # Approved
        return ResolutionResult(
            approved=True,
            final_score=weighted_score,
            decision_reason="Approved by weighted consensus",
            blocking_issues=[],
            action="approve"
        )

    def _parse_review(self, data: Dict[str, Any], agent_id: str) -> ReviewResult:
        """Extract standardized fields from review data."""
        # Handle AgentFeedback object (dict representation) or raw dict
        if hasattr(data, "score"): # It's an object
            return ReviewResult(
                approved=data.approved,
                score=data.score,
                blocking_issues=data.blocking_issues,
                agent_id=agent_id
            )
        
        # It's a dict
        return ReviewResult(
            approved=data.get("approved", False),
            score=float(data.get("score", 0.0)),
            blocking_issues=data.get("blocking_issues", []),
            agent_id=agent_id
        )

    def _check_authority_veto(self, blockers: List[Dict[str, Any]]) -> Optional[str]:
        """Check if any blocker is from the authority for that domain."""
        for item in blockers:
            agent = item["agent"]
            issue_text = str(item["issue"]).lower()
            
            # Check keywords against domains
            for domain, authority in self.DOMAIN_AUTHORITY.items():
                if domain in issue_text and agent == authority:
                    return f"{agent.title()} flagged {domain.upper()} issue: {item['issue']}"
        
        return None