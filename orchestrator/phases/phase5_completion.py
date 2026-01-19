"""Phase 5: Completion - Summary generation and next steps."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .base import BasePhase


class CompletionPhase(BasePhase):
    """Phase 5: Completion.

    Generates final summary and recommendations:
    - Collects metrics from all phases
    - Generates completion summary
    - Provides next steps recommendations

    Creates:
    - completion-summary.json: Structured summary
    - COMPLETION.md: Human-readable summary
    - metrics.json: Workflow metrics
    """

    phase_number = 5
    phase_name = "completion"

    def execute(self) -> dict:
        """Execute the completion phase.

        Returns:
            Dictionary with completion results
        """
        self.logger.info("Generating completion summary", phase=5)

        # Gather data from all phases
        plan = self.get_plan()
        feedback = self.get_feedback()
        impl_results = self.get_implementation_results()
        verification = self._get_verification_results()

        # Collect metrics
        metrics = self._collect_metrics()
        self.write_file(self.phase_dir / "metrics.json", metrics)

        # Generate summary
        summary = self._generate_summary(plan, feedback, impl_results, verification, metrics)
        self.write_file(self.phase_dir / "completion-summary.json", summary)

        # Generate human-readable completion report
        completion_md = self._generate_completion_markdown(summary)
        self.write_file(self.phase_dir / "COMPLETION.md", completion_md)

        # Also write to project root for visibility
        self.write_file(self.project_dir / "WORKFLOW-SUMMARY.md", completion_md)

        self.logger.success("Workflow completed successfully", phase=5)

        return {
            "success": True,
            "summary": summary,
            "metrics": metrics,
            "summary_file": str(self.phase_dir / "completion-summary.json"),
            "completion_md": str(self.phase_dir / "COMPLETION.md"),
        }

    def _get_verification_results(self) -> Optional[dict]:
        """Get verification results from phase 4."""
        verification_file = self.state.get_phase_dir(4) / "verification-results.json"
        return self.read_json(verification_file)

    def _collect_metrics(self) -> dict:
        """Collect metrics from all phases."""
        metrics = {
            "workflow": {
                "started_at": self.state.state.created_at,
                "completed_at": datetime.now().isoformat(),
                "total_phases": 5,
                "phases_completed": 0,
                "total_commits": len(self.state.state.git_commits),
            },
            "phases": {},
            "agents": {
                "claude": {"tasks": 0, "duration_seconds": 0},
                "cursor": {"tasks": 0, "duration_seconds": 0},
                "gemini": {"tasks": 0, "duration_seconds": 0},
            },
            "code": {
                "files_created": 0,
                "files_modified": 0,
                "tests_written": 0,
                "tests_passed": 0,
                "tests_failed": 0,
            },
        }

        # Collect phase metrics
        for phase_name, phase_state in self.state.state.phases.items():
            if phase_state.status.value == "completed":
                metrics["workflow"]["phases_completed"] += 1

            phase_metrics = {
                "status": phase_state.status.value,
                "attempts": phase_state.attempts,
                "started_at": phase_state.started_at,
                "completed_at": phase_state.completed_at,
            }

            # Calculate duration if available
            if phase_state.started_at and phase_state.completed_at:
                try:
                    start = datetime.fromisoformat(phase_state.started_at)
                    end = datetime.fromisoformat(phase_state.completed_at)
                    phase_metrics["duration_seconds"] = (end - start).total_seconds()
                except Exception:
                    pass

            metrics["phases"][phase_name] = phase_metrics

        # Collect implementation metrics
        impl_results = self.get_implementation_results()
        if impl_results:
            metrics["code"]["files_created"] = len(impl_results.get("files_created", []))
            metrics["code"]["files_modified"] = len(impl_results.get("files_modified", []))
            metrics["code"]["tests_written"] = len(impl_results.get("tests_written", []))

            test_results = impl_results.get("test_results", {})
            metrics["code"]["tests_passed"] = test_results.get("passed", 0)
            metrics["code"]["tests_failed"] = test_results.get("failed", 0)

        # Agent involvement
        metrics["agents"]["claude"]["tasks"] = 2  # Planning + Implementation
        metrics["agents"]["cursor"]["tasks"] = 2  # Validation + Verification
        metrics["agents"]["gemini"]["tasks"] = 2  # Validation + Verification

        return metrics

    def _generate_summary(
        self,
        plan: Optional[dict],
        feedback: Optional[dict],
        impl_results: Optional[dict],
        verification: Optional[dict],
        metrics: dict,
    ) -> dict:
        """Generate structured completion summary."""
        summary = {
            "project": self.state.state.project_name,
            "feature": plan.get("plan_name", "Unknown") if plan else "Unknown",
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "overview": {
                "plan_summary": plan.get("summary", "") if plan else "",
                "complexity": plan.get("estimated_complexity", "unknown") if plan else "unknown",
            },
            "validation": {
                "recommendation": feedback.get("recommendation", "unknown") if feedback else "unknown",
                "concerns_addressed": len(feedback.get("all_concerns", [])) if feedback else 0,
            },
            "implementation": {
                "completed": impl_results.get("implementation_complete", False) if impl_results else False,
                "files_created": impl_results.get("files_created", []) if impl_results else [],
                "files_modified": impl_results.get("files_modified", []) if impl_results else [],
            },
            "verification": {
                "approved": verification.get("reviews", {}).get("cursor", {}).get("approved", False) and
                            verification.get("reviews", {}).get("gemini", {}).get("approved", False)
                            if verification else False,
                "code_quality_score": verification.get("code_quality_score", 0) if verification else 0,
                "architecture_score": verification.get("architecture_score", 0) if verification else 0,
            },
            "tests": {
                "passed": metrics["code"]["tests_passed"],
                "failed": metrics["code"]["tests_failed"],
                "all_passed": metrics["code"]["tests_failed"] == 0 and metrics["code"]["tests_passed"] > 0,
            },
            "git": {
                "commits": len(self.state.state.git_commits),
                "commit_hashes": [c.get("hash", "")[:8] for c in self.state.state.git_commits],
            },
            "metrics": metrics,
            "next_steps": self._generate_next_steps(verification),
        }

        return summary

    def _generate_next_steps(self, verification: Optional[dict]) -> list[str]:
        """Generate recommended next steps."""
        next_steps = []

        if not verification:
            next_steps.append("Review verification results and address any issues")
            return next_steps

        blocking = verification.get("blocking_issues", [])
        if blocking:
            next_steps.append("Address blocking issues before merging:")
            for issue in blocking[:3]:  # Top 3
                next_steps.append(f"  - {issue.get('description', 'Unknown issue')}")

        warnings = verification.get("warnings", [])
        if warnings:
            next_steps.append(f"Review {len(warnings)} warning(s) for potential improvements")

        # Standard next steps
        next_steps.extend([
            "Run full test suite to confirm all tests pass",
            "Update documentation if needed",
            "Create pull request for review",
            "Plan for deployment and monitoring",
        ])

        return next_steps

    def _generate_completion_markdown(self, summary: dict) -> str:
        """Generate human-readable completion report."""
        lines = [
            f"# Workflow Completion Summary",
            "",
            f"**Project:** {summary['project']}",
            f"**Feature:** {summary['feature']}",
            f"**Completed:** {summary['completed_at']}",
            "",
            "---",
            "",
            "## Overview",
            "",
            summary["overview"]["plan_summary"] or "No summary available.",
            "",
            f"**Complexity:** {summary['overview']['complexity']}",
            "",
            "---",
            "",
            "## Phase Results",
            "",
            "| Phase | Status | Result |",
            "|-------|--------|--------|",
        ]

        # Add phase statuses
        metrics = summary.get("metrics", {})
        phases = metrics.get("phases", {})
        for phase_name, phase_data in phases.items():
            status = phase_data.get("status", "unknown")
            emoji = "✅" if status == "completed" else "❌" if status == "failed" else "⏳"
            lines.append(f"| {phase_name.title()} | {emoji} {status} | - |")

        lines.extend([
            "",
            "---",
            "",
            "## Implementation Summary",
            "",
            f"- **Files Created:** {len(summary['implementation']['files_created'])}",
            f"- **Files Modified:** {len(summary['implementation']['files_modified'])}",
            f"- **Tests Passed:** {summary['tests']['passed']}",
            f"- **Tests Failed:** {summary['tests']['failed']}",
            "",
        ])

        if summary["implementation"]["files_created"]:
            lines.append("### New Files")
            for f in summary["implementation"]["files_created"][:10]:
                lines.append(f"- `{f}`")
            if len(summary["implementation"]["files_created"]) > 10:
                lines.append(f"- ... and {len(summary['implementation']['files_created']) - 10} more")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## Verification Results",
            "",
            f"**Approved:** {'✅ Yes' if summary['verification']['approved'] else '❌ No'}",
            "",
            f"| Metric | Score |",
            f"|--------|-------|",
            f"| Code Quality | {summary['verification']['code_quality_score']}/10 |",
            f"| Architecture | {summary['verification']['architecture_score']}/10 |",
            "",
            "---",
            "",
            "## Git Activity",
            "",
            f"**Total Commits:** {summary['git']['commits']}",
            "",
        ])

        if summary["git"]["commit_hashes"]:
            lines.append("**Commit Hashes:**")
            for h in summary["git"]["commit_hashes"]:
                lines.append(f"- `{h}`")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## Next Steps",
            "",
        ])

        for step in summary.get("next_steps", []):
            if step.startswith("  -"):
                lines.append(step)
            else:
                lines.append(f"- {step}")

        lines.extend([
            "",
            "---",
            "",
            "*Generated by Multi-Agent Orchestration System*",
        ])

        return "\n".join(lines)
