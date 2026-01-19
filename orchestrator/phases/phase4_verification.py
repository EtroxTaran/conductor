"""Phase 4: Verification - Cursor and Gemini verify the implementation in parallel."""

import json
import concurrent.futures
from pathlib import Path
from typing import Optional

from .base import BasePhase
from ..agents.base import AgentResult
from ..utils.approval import ApprovalEngine, ApprovalConfig, ApprovalPolicy
from ..utils.conflict_resolution import ConflictResolver, ResolutionStrategy


class VerificationPhase(BasePhase):
    """Phase 4: Verification.

    Cursor and Gemini verify the implementation in parallel:
    - Cursor: Code review (bugs, security, style)
    - Gemini: Architecture review (design, scalability, technical debt)

    Creates:
    - cursor-review.json: Cursor's code review
    - gemini-review.json: Gemini's architecture review
    - verification-results.json: Combined verification results
    - ready-to-merge.json: Final approval status
    """

    phase_number = 4
    phase_name = "verification"

    def __init__(self, *args, **kwargs):
        """Initialize verification phase with approval and conflict engines."""
        super().__init__(*args, **kwargs)

        # Initialize engines with phase-specific configurations
        # Verification phase uses stricter ALL_MUST_APPROVE policy
        self.approval_engine = ApprovalEngine()
        self.conflict_resolver = ConflictResolver(
            default_strategy=ResolutionStrategy.CONSERVATIVE
        )

    def execute(self) -> dict:
        """Execute the verification phase.

        Returns:
            Dictionary with verification results
        """
        # Get implementation results
        impl_results = self.get_implementation_results()
        if not impl_results:
            return {
                "success": False,
                "error": "Implementation results not found. Phase 3 must complete first.",
            }

        plan = self.get_plan()
        if not plan:
            return {
                "success": False,
                "error": "plan.json not found.",
            }

        # Get list of files changed
        files_changed = (
            impl_results.get("files_created", []) +
            impl_results.get("files_modified", [])
        )

        if not files_changed:
            self.logger.warning("No files to review", phase=4)
            # Try to detect files from git
            files_changed = self._get_changed_files_from_git()

        test_results = impl_results.get("test_results", {})

        self.logger.info("Starting parallel verification", phase=4)

        # Run reviewers in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            cursor_future = executor.submit(
                self._run_cursor_review, files_changed, test_results
            )
            gemini_future = executor.submit(
                self._run_gemini_review, files_changed, plan
            )

            cursor_result = cursor_future.result()
            gemini_result = gemini_future.result()

        # Process results
        cursor_review = self._process_result("cursor", cursor_result)
        gemini_review = self._process_result("gemini", gemini_result)

        # Save individual reviews
        if cursor_review:
            self.write_file(self.phase_dir / "cursor-review.json", cursor_review)
            self.logger.info("Saved cursor-review.json", phase=4)

        if gemini_review:
            self.write_file(self.phase_dir / "gemini-review.json", gemini_review)
            self.logger.info("Saved gemini-review.json", phase=4)

        # Combine verification results
        verification = self._combine_verification(cursor_review, gemini_review)
        self.write_file(self.phase_dir / "verification-results.json", verification)

        # Detect and resolve conflicts
        conflict_result = self.conflict_resolver.resolve_all(
            cursor_review, gemini_review
        )
        if conflict_result.has_conflicts:
            self.logger.info(
                f"Detected {len(conflict_result.conflicts)} conflict(s), "
                f"{conflict_result.unresolved_count} unresolved",
                phase=4
            )
            verification["conflicts"] = conflict_result.to_dict()

        # Determine final approval using approval engine
        approval_result = self.approval_engine.evaluate_for_verification(
            cursor_review, gemini_review
        )
        approved = approval_result.approved

        ready_to_merge = {
            "approved": approved,
            "cursor_approved": approval_result.cursor_approved,
            "gemini_approved": approval_result.gemini_approved,
            "combined_score": approval_result.combined_score,
            "blocking_issues": verification.get("blocking_issues", []),
            "approval_reasoning": approval_result.reasoning,
            "policy_used": approval_result.policy_used.value,
            "timestamp": self._get_timestamp(),
        }
        self.write_file(self.phase_dir / "ready-to-merge.json", ready_to_merge)

        # Save detailed approval result
        self.write_file(
            self.phase_dir / "approval-result.json",
            approval_result.to_dict()
        )

        if approved:
            self.logger.success(
                f"Implementation verified and approved ({approval_result.reasoning})",
                phase=4
            )
        else:
            self.logger.warning(
                f"Implementation needs changes ({approval_result.reasoning})",
                phase=4
            )

        return {
            "success": True,
            "approved": approved,
            "cursor_review": cursor_review,
            "gemini_review": gemini_review,
            "blocking_issues": ready_to_merge["blocking_issues"],
            "approval_result": approval_result.to_dict(),
            "conflict_result": conflict_result.to_dict() if conflict_result.has_conflicts else None,
            "verification_file": str(self.phase_dir / "verification-results.json"),
        }

    def _run_cursor_review(
        self,
        files_changed: list[str],
        test_results: dict,
    ) -> AgentResult:
        """Run Cursor code review."""
        self.logger.agent_start("cursor", "Code review", phase=4)

        result = self.cursor.run_code_review(
            files_changed=files_changed,
            test_results=test_results,
            output_file=self.phase_dir / "cursor-review.json",
        )

        if result.success:
            self.logger.agent_complete("cursor", "Code review complete", phase=4)
        else:
            self.logger.agent_error("cursor", result.error or "Review failed", phase=4)

        return result

    def _run_gemini_review(
        self,
        files_changed: list[str],
        plan: dict,
    ) -> AgentResult:
        """Run Gemini architecture review."""
        self.logger.agent_start("gemini", "Architecture review", phase=4)

        result = self.gemini.run_architecture_review(
            files_changed=files_changed,
            plan=plan,
            output_file=self.phase_dir / "gemini-review.json",
        )

        if result.success:
            self.logger.agent_complete("gemini", "Architecture review complete", phase=4)
        else:
            self.logger.agent_error("gemini", result.error or "Review failed", phase=4)

        return result

    def _process_result(self, agent: str, result: AgentResult) -> Optional[dict]:
        """Process agent result and extract review."""
        if result.success and result.parsed_output:
            return result.parsed_output

        if result.output:
            try:
                import re
                json_pattern = r'\{[\s\S]*"reviewer"[\s\S]*\}'
                matches = re.findall(json_pattern, result.output)
                for match in matches:
                    try:
                        return json.loads(match)
                    except json.JSONDecodeError:
                        continue
            except Exception:
                pass

        return {
            "reviewer": agent,
            "approved": False,
            "error": result.error or "Failed to get review",
        }

    def _combine_verification(
        self,
        cursor_review: Optional[dict],
        gemini_review: Optional[dict],
    ) -> dict:
        """Combine verification results from both reviewers."""
        verification = {
            "reviews": {
                "cursor": cursor_review or {"error": "No review received"},
                "gemini": gemini_review or {"error": "No review received"},
            },
            "blocking_issues": [],
            "warnings": [],
            "code_quality_score": 0,
            "architecture_score": 0,
        }

        # Extract blocking issues from Cursor
        if cursor_review:
            verification["code_quality_score"] = cursor_review.get("overall_code_quality", 0)

            for issue in cursor_review.get("blocking_issues", []):
                verification["blocking_issues"].append({
                    "source": "cursor",
                    "type": "code_review",
                    "description": issue,
                })

            # Check files for blocking issues
            for file_review in cursor_review.get("files_reviewed", []):
                for issue in file_review.get("issues", []):
                    if issue.get("severity") == "error":
                        verification["blocking_issues"].append({
                            "source": "cursor",
                            "type": issue.get("type", "unknown"),
                            "file": file_review.get("file"),
                            "line": issue.get("line"),
                            "description": issue.get("description"),
                        })
                    else:
                        verification["warnings"].append({
                            "source": "cursor",
                            "type": issue.get("type", "unknown"),
                            "file": file_review.get("file"),
                            "description": issue.get("description"),
                        })

        # Extract blocking issues from Gemini
        if gemini_review:
            arch_assessment = gemini_review.get("architecture_assessment", {})
            verification["architecture_score"] = arch_assessment.get("modularity_score", 0)

            for issue in gemini_review.get("blocking_issues", []):
                verification["blocking_issues"].append({
                    "source": "gemini",
                    "type": "architecture",
                    "description": issue,
                })

            # Check technical debt
            tech_debt = gemini_review.get("technical_debt", {})
            for item in tech_debt.get("items", []):
                if item.get("severity") == "high":
                    verification["blocking_issues"].append({
                        "source": "gemini",
                        "type": "technical_debt",
                        "description": item.get("description"),
                    })

        # Calculate overall scores
        scores = [
            verification["code_quality_score"],
            verification["architecture_score"],
        ]
        valid_scores = [s for s in scores if s > 0]
        verification["overall_score"] = (
            sum(valid_scores) / len(valid_scores) if valid_scores else 0
        )

        return verification

    def _check_approval(
        self,
        cursor_review: Optional[dict],
        gemini_review: Optional[dict],
    ) -> bool:
        """Check if both reviewers approve.

        Note: This method is kept for backward compatibility.
        The main approval logic now uses ApprovalEngine in execute().
        """
        cursor_approved = cursor_review.get("approved", False) if cursor_review else False
        gemini_approved = gemini_review.get("approved", False) if gemini_review else False

        return cursor_approved and gemini_approved

    def get_approval_config(self) -> ApprovalConfig:
        """Get the approval configuration for this phase.

        Can be overridden to customize approval behavior.
        """
        return self.approval_engine.get_config(self.phase_number)

    def set_approval_config(self, config: ApprovalConfig) -> None:
        """Set custom approval configuration for this phase."""
        self.approval_engine.configs[self.phase_number] = config

    def _get_changed_files_from_git(self) -> list[str]:
        """Get list of changed files from git."""
        import subprocess

        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout.strip().split("\n")
        except Exception:
            pass

        # Try getting staged files
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout.strip().split("\n")
        except Exception:
            pass

        return []

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
