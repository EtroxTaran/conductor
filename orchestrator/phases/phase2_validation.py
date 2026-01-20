"""Phase 2: Validation - Cursor and Gemini validate the plan in parallel."""

import json
import concurrent.futures
from pathlib import Path
from typing import Optional, Tuple

from .base import BasePhase
from ..agents.base import AgentResult
from ..utils.approval import ApprovalEngine, ApprovalConfig, ApprovalPolicy
from ..utils.conflict_resolution import ConflictResolver, ResolutionStrategy
from ..utils.validation import validate_feedback

# Unified timeout for parallel validation (5 minutes)
# Uses single timeout via wait() to avoid timeout stacking issues
PARALLEL_TIMEOUT = 300


class ValidationPhase(BasePhase):
    """Phase 2: Validation.

    Cursor and Gemini review the plan in parallel:
    - Cursor focuses on code quality, security, maintainability
    - Gemini focuses on architecture, scalability, design patterns

    Creates:
    - cursor-feedback.json: Cursor's review
    - gemini-feedback.json: Gemini's review
    - consolidated-feedback.md: Combined human-readable feedback
    - consolidated-feedback.json: Combined structured feedback
    """

    phase_number = 2
    phase_name = "validation"

    def __init__(self, *args, **kwargs):
        """Initialize validation phase with approval and conflict engines."""
        super().__init__(*args, **kwargs)

        # Initialize engines with phase-specific configurations
        self.approval_engine = ApprovalEngine()
        self.conflict_resolver = ConflictResolver(
            default_strategy=ResolutionStrategy.WEIGHTED
        )

    def execute(self) -> dict:
        """Execute the validation phase.

        Returns:
            Dictionary with validation results
        """
        # Get the plan from phase 1
        plan = self.get_plan()
        if not plan:
            return {
                "success": False,
                "error": "plan.json not found. Phase 1 must complete first.",
            }

        self.logger.info("Starting parallel validation", phase=2)

        # Run validators in parallel with proper exception handling
        cursor_result, gemini_result = self._run_parallel_validation(plan)

        # Process results
        cursor_feedback = self._process_result("cursor", cursor_result)
        gemini_feedback = self._process_result("gemini", gemini_result)

        # Save individual feedback
        if cursor_feedback:
            self.write_file(self.phase_dir / "cursor-feedback.json", cursor_feedback)
            self.logger.info("Saved cursor-feedback.json", phase=2)

        if gemini_feedback:
            self.write_file(self.phase_dir / "gemini-feedback.json", gemini_feedback)
            self.logger.info("Saved gemini-feedback.json", phase=2)

        # Consolidate feedback
        consolidated = self._consolidate_feedback(cursor_feedback, gemini_feedback)
        self.write_file(self.phase_dir / "consolidated-feedback.json", consolidated)

        # Generate human-readable consolidated feedback
        consolidated_md = self._generate_feedback_markdown(consolidated)
        self.write_file(self.phase_dir / "consolidated-feedback.md", consolidated_md)
        self.logger.info("Generated consolidated feedback", phase=2)

        # Detect and resolve conflicts
        conflict_result = self.conflict_resolver.resolve_all(
            cursor_feedback, gemini_feedback
        )
        if conflict_result.has_conflicts:
            self.logger.info(
                f"Detected {len(conflict_result.conflicts)} conflict(s), "
                f"{conflict_result.unresolved_count} unresolved",
                phase=2
            )
            consolidated["conflicts"] = conflict_result.to_dict()

        # Determine overall approval using approval engine
        approval_result = self.approval_engine.evaluate_for_validation(
            cursor_feedback, gemini_feedback
        )
        overall_approved = approval_result.approved

        # Save approval result
        self.write_file(
            self.phase_dir / "approval-result.json",
            approval_result.to_dict()
        )

        if overall_approved:
            self.logger.success(
                f"Plan validated and approved ({approval_result.reasoning})",
                phase=2
            )
        else:
            self.logger.warning(
                f"Plan needs changes ({approval_result.reasoning})",
                phase=2
            )

        # Increment iteration count if not approved
        if not overall_approved:
            self.state.increment_iteration()

        return {
            "success": True,
            "approved": overall_approved,
            "cursor_feedback": cursor_feedback,
            "gemini_feedback": gemini_feedback,
            "consolidated": consolidated,
            "approval_result": approval_result.to_dict(),
            "conflict_result": conflict_result.to_dict() if conflict_result.has_conflicts else None,
            "feedback_file": str(self.phase_dir / "consolidated-feedback.json"),
        }

    def _run_parallel_validation(self, plan: dict) -> Tuple[AgentResult, AgentResult]:
        """Run validators in parallel with unified timeout handling.

        Uses concurrent.futures.wait() with a single timeout to avoid
        timeout stacking issues (previously had as_completed + future.result
        timeouts which caused unpredictable behavior).

        Args:
            plan: The plan to validate

        Returns:
            Tuple of (cursor_result, gemini_result)
        """
        results: dict[str, AgentResult] = {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_to_agent = {
                executor.submit(self._run_cursor_validation, plan): "cursor",
                executor.submit(self._run_gemini_validation, plan): "gemini",
            }

            # Single unified timeout using wait()
            done, not_done = concurrent.futures.wait(
                future_to_agent.keys(),
                timeout=PARALLEL_TIMEOUT,
                return_when=concurrent.futures.ALL_COMPLETED
            )

            # Process completed futures (no additional timeout needed)
            for future in done:
                agent = future_to_agent[future]
                try:
                    results[agent] = future.result()  # Already completed, no timeout
                except Exception as e:
                    self.logger.error(f"{agent} validation failed: {e}", phase=2)
                    results[agent] = AgentResult(
                        success=False,
                        error=f"Validation failed: {str(e)}"
                    )

            # Handle timed-out futures
            for future in not_done:
                agent = future_to_agent[future]
                future.cancel()
                self.logger.error(f"{agent} validation timed out", phase=2)
                results[agent] = AgentResult(
                    success=False,
                    error=f"Validation timed out after {PARALLEL_TIMEOUT} seconds"
                )

        # Ensure we always return valid results
        cursor_result = results.get("cursor") or AgentResult(
            success=False, error="No result received from cursor"
        )
        gemini_result = results.get("gemini") or AgentResult(
            success=False, error="No result received from gemini"
        )

        return cursor_result, gemini_result

    def _run_cursor_validation(self, plan: dict) -> AgentResult:
        """Run Cursor validation."""
        self.logger.agent_start("cursor", "Validating plan (code quality focus)", phase=2)

        result = self.cursor.run_validation(
            plan=plan,
            output_file=self.phase_dir / "cursor-feedback.json",
        )

        if result.success:
            self.logger.agent_complete("cursor", "Plan review complete", phase=2)
        else:
            self.logger.agent_error("cursor", result.error or "Validation failed", phase=2)

        return result

    def _run_gemini_validation(self, plan: dict) -> AgentResult:
        """Run Gemini validation."""
        self.logger.agent_start("gemini", "Validating plan (architecture focus)", phase=2)

        result = self.gemini.run_validation(
            plan=plan,
            output_file=self.phase_dir / "gemini-feedback.json",
        )

        if result.success:
            self.logger.agent_complete("gemini", "Architecture review complete", phase=2)
        else:
            self.logger.agent_error("gemini", result.error or "Validation failed", phase=2)

        return result

    def _process_result(self, agent: str, result: AgentResult) -> Optional[dict]:
        """Process agent result and extract feedback with validation.

        Uses the validate_feedback function to ensure consistent output
        format regardless of agent response variations.
        """
        # If we have parsed output, validate and normalize it
        if result.success and result.parsed_output:
            return validate_feedback(agent, result.parsed_output)

        # Try to extract JSON from raw output
        if result.output:
            try:
                import re
                json_pattern = r'\{[\s\S]*"reviewer"[\s\S]*\}'
                matches = re.findall(json_pattern, result.output)
                for match in matches:
                    try:
                        parsed = json.loads(match)
                        return validate_feedback(agent, parsed)
                    except json.JSONDecodeError:
                        continue
            except Exception as e:
                self.logger.warning(f"Failed to extract JSON from {agent} output: {e}", phase=2)

        # Return minimal validated feedback if extraction failed
        return validate_feedback(agent, {
            "error": result.error or "Failed to get feedback"
        })

    def _consolidate_feedback(
        self,
        cursor_feedback: Optional[dict],
        gemini_feedback: Optional[dict],
    ) -> dict:
        """Consolidate feedback from both validators."""
        consolidated = {
            "validators": {
                "cursor": cursor_feedback or {"error": "No feedback received"},
                "gemini": gemini_feedback or {"error": "No feedback received"},
            },
            "summary": {
                "cursor_assessment": (cursor_feedback or {}).get("overall_assessment", "unknown"),
                "gemini_assessment": (gemini_feedback or {}).get("overall_assessment", "unknown"),
                "cursor_score": (cursor_feedback or {}).get("score", 0),
                "gemini_score": (gemini_feedback or {}).get("score", 0),
            },
            "all_concerns": [],
            "all_strengths": [],
            "blocking_issues": [],
        }

        # Aggregate concerns
        if cursor_feedback and "concerns" in cursor_feedback:
            for concern in cursor_feedback["concerns"]:
                if isinstance(concern, dict):
                    concern["source"] = "cursor"
                    consolidated["all_concerns"].append(concern)
                    if concern.get("severity") == "high":
                        consolidated["blocking_issues"].append(concern)

        if gemini_feedback:
            arch_review = gemini_feedback.get("architecture_review", {})
            for concern in arch_review.get("concerns", []):
                if isinstance(concern, dict):
                    concern["source"] = "gemini"
                    consolidated["all_concerns"].append(concern)

        # Aggregate strengths
        if cursor_feedback and "strengths" in cursor_feedback:
            for strength in cursor_feedback["strengths"]:
                consolidated["all_strengths"].append({
                    "source": "cursor",
                    "strength": strength,
                })

        # Calculate overall recommendation
        cursor_approved = (cursor_feedback or {}).get("overall_assessment") == "approve"
        gemini_approved = (gemini_feedback or {}).get("overall_assessment") == "approve"

        if cursor_approved and gemini_approved:
            consolidated["recommendation"] = "proceed"
        elif not cursor_approved and not gemini_approved:
            consolidated["recommendation"] = "revise_plan"
        else:
            consolidated["recommendation"] = "review_concerns"

        return consolidated

    def _check_approval(self, consolidated: dict) -> bool:
        """Check if plan is approved for implementation.

        Note: This method is kept for backward compatibility.
        The main approval logic now uses ApprovalEngine in execute().
        """
        recommendation = consolidated.get("recommendation", "")

        # Block if there are high-severity concerns
        if consolidated.get("blocking_issues"):
            return False

        # Proceed only if both validators approve or recommendation is to proceed
        return recommendation == "proceed"

    def get_approval_config(self) -> ApprovalConfig:
        """Get the approval configuration for this phase.

        Can be overridden to customize approval behavior.
        """
        return self.approval_engine.get_config(self.phase_number)

    def set_approval_config(self, config: ApprovalConfig) -> None:
        """Set custom approval configuration for this phase."""
        self.approval_engine.configs[self.phase_number] = config

    def _generate_feedback_markdown(self, consolidated: dict) -> str:
        """Generate human-readable feedback markdown."""
        lines = [
            "# Plan Validation Results",
            "",
            "## Summary",
            "",
        ]

        summary = consolidated.get("summary", {})
        lines.extend([
            f"| Validator | Assessment | Score |",
            f"|-----------|------------|-------|",
            f"| Cursor | {summary.get('cursor_assessment', 'N/A')} | {summary.get('cursor_score', 'N/A')}/10 |",
            f"| Gemini | {summary.get('gemini_assessment', 'N/A')} | {summary.get('gemini_score', 'N/A')}/10 |",
            "",
            f"**Recommendation:** {consolidated.get('recommendation', 'N/A').replace('_', ' ').title()}",
            "",
        ])

        # Blocking issues
        blocking = consolidated.get("blocking_issues", [])
        if blocking:
            lines.extend([
                "---",
                "",
                "## ⚠️ Blocking Issues",
                "",
                "These must be addressed before proceeding:",
                "",
            ])
            for issue in blocking:
                lines.extend([
                    f"### {issue.get('area', 'Issue')} ({issue.get('source', 'unknown')})",
                    "",
                    issue.get("description", "No description"),
                    "",
                    f"**Suggestion:** {issue.get('suggestion', issue.get('recommendation', 'N/A'))}",
                    "",
                ])

        # All concerns
        concerns = consolidated.get("all_concerns", [])
        if concerns:
            lines.extend([
                "---",
                "",
                "## Concerns",
                "",
            ])
            for concern in concerns:
                severity = concern.get("severity", "unknown")
                emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
                lines.extend([
                    f"### {emoji} {concern.get('area', 'Concern')}",
                    "",
                    f"**Severity:** {severity} | **Source:** {concern.get('source', 'unknown')}",
                    "",
                    concern.get("description", "No description"),
                    "",
                ])
                if concern.get("suggestion") or concern.get("recommendation"):
                    lines.append(f"**Suggestion:** {concern.get('suggestion', concern.get('recommendation', ''))}")
                    lines.append("")

        # Strengths
        strengths = consolidated.get("all_strengths", [])
        if strengths:
            lines.extend([
                "---",
                "",
                "## Strengths",
                "",
            ])
            for s in strengths:
                lines.append(f"- ✅ {s.get('strength', s)} ({s.get('source', 'unknown')})")
            lines.append("")

        # Detailed feedback sections
        validators = consolidated.get("validators", {})

        # Cursor details
        cursor = validators.get("cursor", {})
        if cursor and "security_review" in cursor:
            sec = cursor["security_review"]
            if sec.get("issues") or sec.get("recommendations"):
                lines.extend([
                    "---",
                    "",
                    "## Security Review (Cursor)",
                    "",
                ])
                for issue in sec.get("issues", []):
                    lines.append(f"- ⚠️ {issue}")
                for rec in sec.get("recommendations", []):
                    lines.append(f"- 💡 {rec}")
                lines.append("")

        # Gemini architecture details
        gemini = validators.get("gemini", {})
        if gemini and "architecture_review" in gemini:
            arch = gemini["architecture_review"]
            lines.extend([
                "---",
                "",
                "## Architecture Review (Gemini)",
                "",
                f"**Scalability:** {arch.get('scalability_assessment', 'N/A')}",
                "",
                f"**Maintainability:** {arch.get('maintainability_assessment', 'N/A')}",
                "",
            ])
            if arch.get("patterns_identified"):
                lines.append("**Patterns Identified:**")
                for p in arch["patterns_identified"]:
                    lines.append(f"- {p}")
                lines.append("")

        # Alternative approaches
        if gemini and "alternative_approaches" in gemini:
            alts = gemini["alternative_approaches"]
            if alts:
                lines.extend([
                    "---",
                    "",
                    "## Alternative Approaches Suggested",
                    "",
                ])
                for alt in alts:
                    lines.extend([
                        f"### {alt.get('approach', 'Alternative')}",
                        "",
                        "**Pros:**",
                    ])
                    for pro in alt.get("pros", []):
                        lines.append(f"- {pro}")
                    lines.append("")
                    lines.append("**Cons:**")
                    for con in alt.get("cons", []):
                        lines.append(f"- {con}")
                    lines.append("")
                    if alt.get("recommendation"):
                        lines.append(f"**When to consider:** {alt['recommendation']}")
                        lines.append("")

        return "\n".join(lines)
