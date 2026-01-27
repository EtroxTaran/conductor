"""Conflict Resolver for 4-Eyes Verification Protocol.

Resolves disagreements between reviewers (Cursor/Security vs Gemini/Architecture)
using weighted authority based on domain expertise.

Keyword matching uses compiled regex patterns with word boundaries to avoid
false positives from substring matching (e.g., "injection" matching "rejection").
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _compile_pattern(keyword: str) -> re.Pattern:
    """Compile keyword into regex pattern with word boundaries.

    Args:
        keyword: Keyword to match (can contain spaces)

    Returns:
        Compiled regex pattern
    """
    # Escape special characters and add word boundaries
    escaped = re.escape(keyword)
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


def _compile_patterns(keywords: list[str]) -> list[re.Pattern]:
    """Compile multiple keywords into regex patterns."""
    return [_compile_pattern(k) for k in keywords]


@dataclass
class ReviewResult:
    """Standardized review result."""

    approved: bool
    score: float
    blocking_issues: list[str]
    agent_id: str


@dataclass
class ResolutionResult:
    """Result of conflict resolution."""

    approved: bool
    final_score: float
    decision_reason: str
    blocking_issues: list[dict[str, Any]]
    action: str  # "approve", "reject", "escalate"


class ConflictResolver:
    """Resolves verification conflicts using weighted domain expertise.

    Uses compiled regex patterns for keyword matching to avoid false positives
    from naive substring matching.
    """

    # Weights for overall score calculation
    # Reflects the general reliability/specialization of each agent
    DEFAULT_WEIGHTS = {
        "cursor": 0.6,  # Stronger on code/security/implementation details
        "gemini": 0.4,  # Stronger on high-level architecture/patterns
    }

    # Domain-specific authority patterns with their authority agent
    # NOTE: Only actual vulnerabilities trigger veto, not process/documentation gaps
    # Format: (pattern, authority_agent, domain_name)
    DOMAIN_PATTERNS = [
        # Security vulnerabilities (Cursor authority)
        (_compile_pattern("vulnerability"), "cursor", "vulnerability"),
        (_compile_pattern("sql injection"), "cursor", "sql injection"),
        (_compile_pattern("command injection"), "cursor", "command injection"),
        (_compile_pattern("code injection"), "cursor", "code injection"),
        (_compile_pattern("injection attack"), "cursor", "injection"),
        (_compile_pattern("xss"), "cursor", "xss"),
        (_compile_pattern("cross-site scripting"), "cursor", "xss"),
        (_compile_pattern("csrf"), "cursor", "csrf"),
        (_compile_pattern("cross-site request forgery"), "cursor", "csrf"),
        (_compile_pattern("rce"), "cursor", "rce"),
        (_compile_pattern("remote code execution"), "cursor", "rce"),
        (_compile_pattern("authentication bypass"), "cursor", "authentication bypass"),
        (_compile_pattern("auth bypass"), "cursor", "authentication bypass"),
        (_compile_pattern("authorization bypass"), "cursor", "authorization bypass"),
        (_compile_pattern("authz bypass"), "cursor", "authorization bypass"),
        (_compile_pattern("privilege escalation"), "cursor", "privilege escalation"),
        (_compile_pattern("privesc"), "cursor", "privilege escalation"),
        (_compile_pattern("path traversal"), "cursor", "path traversal"),
        (_compile_pattern("directory traversal"), "cursor", "directory traversal"),
        (_compile_pattern("insecure deserialization"), "cursor", "deserialization"),
        (_compile_pattern("ssrf"), "cursor", "ssrf"),
        (_compile_pattern("server-side request forgery"), "cursor", "ssrf"),
    ]

    # Patterns that indicate process/documentation gaps (not actual vulnerabilities)
    # These should NOT trigger authority veto
    PROCESS_GAP_PATTERNS = _compile_patterns(
        [
            "no security requirements",
            "not specified",
            "missing documentation",
            "lacks documentation",
            "should include",
            "should add",
            "no mention of",
            "not defined",
            "unclear requirements",
            "missing requirements",
            "requirements unclear",
            "consider adding",
            "recommend adding",
            "suggest adding",
            "would benefit from",
            "needs documentation",
            "should document",
        ]
    )

    def __init__(self, weights: Optional[dict[str, float]] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS

    def resolve(
        self,
        cursor_review: dict[str, Any],
        gemini_review: dict[str, Any],
        cursor_weight: Optional[float] = None,
        gemini_weight: Optional[float] = None,
    ) -> ResolutionResult:
        """Resolve verification results from multiple agents.

        Args:
            cursor_review: Feedback dict from Cursor (A07)
            gemini_review: Feedback dict from Gemini (A08)
            cursor_weight: Optional override for cursor weight (for role dispatch)
            gemini_weight: Optional override for gemini weight (for role dispatch)

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
                action="reject",
            )

        # 3. Calculate Weighted Score
        # Normalize scores to 0-10 range if needed
        s1 = r1.score
        s2 = r2.score

        # Use provided weights (role dispatch) or fall back to defaults
        w1 = cursor_weight if cursor_weight is not None else self.weights.get("cursor", 0.5)
        w2 = gemini_weight if gemini_weight is not None else self.weights.get("gemini", 0.5)

        # Re-normalize weights to sum to 1.0
        total_w = w1 + w2
        w1 = w1 / total_w
        w2 = w2 / total_w

        weighted_score = (s1 * w1) + (s2 * w2)

        # 4. Determine Outcome
        # Phase 2 threshold is 6.0, Phase 4 threshold is 7.0
        # We use 6.0 here as validation happens in Phase 2
        MIN_SCORE = 6.0

        # Filter out process gaps from blocking issues
        # Process gaps are important feedback but shouldn't block validation
        real_blockers = [
            b for b in all_blockers if not self._is_process_gap(str(b["issue"]).lower())
        ]

        # If real blockers exist (actual vulnerabilities), reject regardless of score
        if real_blockers:
            return ResolutionResult(
                approved=False,
                final_score=weighted_score,
                decision_reason=f"Rejected due to {len(real_blockers)} blocking issues (actual vulnerabilities)",
                blocking_issues=real_blockers,
                action="reject",
            )

        # Log process gap warnings (they're feedback, not blockers)
        if all_blockers and not real_blockers:
            logger.warning(
                f"Filtered {len(all_blockers)} process gaps from blocking issues "
                "(these are feedback items, not actual vulnerabilities)"
            )

        # If substantial disagreement (variance > 3.0), escalate
        # We do this before checking the score because a high variance means the score is unreliable
        if abs(s1 - s2) > 3.0:
            return ResolutionResult(
                approved=False,
                final_score=weighted_score,
                decision_reason=f"High disagreement (Diff: {abs(s1-s2):.1f}). Cursor={s1}, Gemini={s2}",
                blocking_issues=[],
                action="escalate",
            )

        # If score is too low, reject
        if weighted_score < MIN_SCORE:
            return ResolutionResult(
                approved=False,
                final_score=weighted_score,
                decision_reason=f"Score {weighted_score:.1f} below threshold {MIN_SCORE}",
                blocking_issues=[],
                action="reject",
            )

        # Approved
        return ResolutionResult(
            approved=True,
            final_score=weighted_score,
            decision_reason="Approved by weighted consensus",
            blocking_issues=[],
            action="approve",
        )

    def _parse_review(self, data: dict[str, Any], agent_id: str) -> ReviewResult:
        """Extract standardized fields from review data."""
        # Handle AgentFeedback object (dict representation) or raw dict
        if hasattr(data, "score"):  # It's an object
            return ReviewResult(
                approved=data.approved,
                score=data.score,
                blocking_issues=data.blocking_issues,
                agent_id=agent_id,
            )

        # It's a dict
        return ReviewResult(
            approved=data.get("approved", False),
            score=float(data.get("score", 0.0)),
            blocking_issues=data.get("blocking_issues", []),
            agent_id=agent_id,
        )

    def _check_authority_veto(self, blockers: list[dict[str, Any]]) -> Optional[str]:
        """Check if any blocker is from the authority for that domain.

        Only triggers veto for actual vulnerabilities, not process/documentation gaps.
        Uses compiled regex patterns with word boundaries for accurate matching.
        """
        for item in blockers:
            agent = item["agent"]
            issue_text = str(item["issue"])

            # Skip if this looks like a process gap rather than actual vulnerability
            if self._is_process_gap(issue_text):
                continue

            # Check patterns against domains
            for pattern, authority, domain_name in self.DOMAIN_PATTERNS:
                if pattern.search(issue_text) and agent == authority:
                    return f"{agent.title()} flagged {domain_name.upper()} issue: {item['issue']}"

        return None

    def _is_process_gap(self, issue_text: str) -> bool:
        """Check if issue text indicates a process gap rather than actual vulnerability.

        Uses compiled regex patterns for accurate matching with word boundaries.
        """
        for pattern in self.PROCESS_GAP_PATTERNS:
            if pattern.search(issue_text):
                return True
        return False
