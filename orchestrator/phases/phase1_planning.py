"""Phase 1: Planning - Claude creates the implementation plan."""

import json
from pathlib import Path
from typing import Optional

from .base import BasePhase
from ..utils.validation import ProductSpecValidator


class PlanningPhase(BasePhase):
    """Phase 1: Planning.

    Claude reads PRODUCT.md and creates:
    - plan.json: Structured implementation plan
    - PLAN.md: Human-readable plan document
    """

    phase_number = 1
    phase_name = "planning"

    def execute(self) -> dict:
        """Execute the planning phase.

        Returns:
            Dictionary with planning results
        """
        # Read product specification
        product_spec = self.get_product_spec()
        if not product_spec:
            return {
                "success": False,
                "error": "PRODUCT.md not found. Please create it with your feature specification.",
            }

        # Validate product specification content
        validator = ProductSpecValidator()
        validation_result = validator.validate(product_spec)

        if not validation_result.valid:
            error_msg = "PRODUCT.md validation failed:\n" + "\n".join(
                f"  - {e}" for e in validation_result.errors
            )
            self.logger.error(error_msg, phase=1)
            return {
                "success": False,
                "error": error_msg,
                "validation_errors": validation_result.errors,
            }

        # Log warnings but continue
        if validation_result.warnings:
            for warning in validation_result.warnings:
                self.logger.warning(f"PRODUCT.md: {warning}", phase=1)

        self.logger.info("Reading product specification", phase=1)
        self.logger.agent_start("claude", "Creating implementation plan", phase=1)

        # Run Claude planning
        result = self.claude.run_planning(
            product_spec=product_spec,
            output_file=self.phase_dir / "plan.json",
        )

        if not result.success:
            self.logger.agent_error("claude", result.error or "Planning failed", phase=1)
            return {
                "success": False,
                "error": result.error or "Claude planning failed",
            }

        # Parse the plan
        plan = result.parsed_output
        if not plan:
            # Try to extract JSON from output
            plan = self._extract_plan_from_output(result.output)

        if not plan:
            self.logger.agent_error("claude", "Failed to parse plan output", phase=1)
            return {
                "success": False,
                "error": "Failed to parse plan from Claude output",
            }

        # Save plan
        self.write_file(self.phase_dir / "plan.json", plan)
        self.logger.info("Saved plan.json", phase=1)

        # Generate human-readable plan
        plan_md = self._generate_plan_markdown(plan)
        self.write_file(self.phase_dir / "PLAN.md", plan_md)
        self.logger.info("Generated PLAN.md", phase=1)

        # Validate plan structure
        validation_errors = self._validate_plan(plan)
        if validation_errors:
            self.logger.warning(f"Plan validation warnings: {validation_errors}", phase=1)

        self.logger.agent_complete("claude", "Implementation plan created", phase=1)

        return {
            "success": True,
            "plan": plan,
            "plan_file": str(self.phase_dir / "plan.json"),
            "plan_md_file": str(self.phase_dir / "PLAN.md"),
            "validation_warnings": validation_errors,
        }

    def _extract_plan_from_output(self, output: Optional[str]) -> Optional[dict]:
        """Try to extract JSON plan from text output."""
        if not output:
            return None

        # Try to find JSON in the output
        import re

        # Look for JSON object pattern
        json_pattern = r'\{[\s\S]*"plan_name"[\s\S]*\}'
        matches = re.findall(json_pattern, output)

        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        return None

    def _validate_plan(self, plan: dict) -> list[str]:
        """Validate plan structure and return list of issues."""
        errors = []

        required_fields = ["plan_name", "summary", "phases"]
        for field in required_fields:
            if field not in plan:
                errors.append(f"Missing required field: {field}")

        if "phases" in plan:
            if not isinstance(plan["phases"], list):
                errors.append("'phases' should be a list")
            elif len(plan["phases"]) == 0:
                errors.append("Plan has no phases defined")
            else:
                for i, phase in enumerate(plan["phases"]):
                    if "tasks" not in phase:
                        errors.append(f"Phase {i+1} has no tasks")
                    elif not phase["tasks"]:
                        errors.append(f"Phase {i+1} has empty tasks list")

        if "test_strategy" not in plan:
            errors.append("Missing test_strategy - TDD approach recommended")

        return errors

    def _generate_plan_markdown(self, plan: dict) -> str:
        """Generate human-readable markdown from plan."""
        lines = [
            f"# Implementation Plan: {plan.get('plan_name', 'Unnamed Plan')}",
            "",
            "## Summary",
            "",
            plan.get("summary", "No summary provided."),
            "",
            "---",
            "",
        ]

        # Phases and tasks
        phases = plan.get("phases", [])
        for phase in phases:
            phase_num = phase.get("phase", "?")
            phase_name = phase.get("name", "Unnamed Phase")
            lines.extend([
                f"## Phase {phase_num}: {phase_name}",
                "",
            ])

            tasks = phase.get("tasks", [])
            for task in tasks:
                task_id = task.get("id", "?")
                desc = task.get("description", "No description")
                files = task.get("files", [])
                deps = task.get("dependencies", [])

                lines.extend([
                    f"### Task {task_id}",
                    "",
                    f"**Description:** {desc}",
                    "",
                ])

                if files:
                    lines.append("**Files:**")
                    for f in files:
                        lines.append(f"- `{f}`")
                    lines.append("")

                if deps:
                    lines.append(f"**Dependencies:** {', '.join(deps)}")
                    lines.append("")

        # Test strategy
        if "test_strategy" in plan:
            ts = plan["test_strategy"]
            lines.extend([
                "---",
                "",
                "## Test Strategy",
                "",
            ])

            if ts.get("unit_tests"):
                lines.append("### Unit Tests")
                for t in ts["unit_tests"]:
                    lines.append(f"- `{t}`")
                lines.append("")

            if ts.get("integration_tests"):
                lines.append("### Integration Tests")
                for t in ts["integration_tests"]:
                    lines.append(f"- `{t}`")
                lines.append("")

            if ts.get("test_commands"):
                lines.append("### Test Commands")
                lines.append("```bash")
                for cmd in ts["test_commands"]:
                    lines.append(cmd)
                lines.append("```")
                lines.append("")

        # Risks
        if "risks" in plan and plan["risks"]:
            lines.extend([
                "---",
                "",
                "## Risks",
                "",
            ])
            for risk in plan["risks"]:
                lines.append(f"- {risk}")
            lines.append("")

        # Complexity
        if "estimated_complexity" in plan:
            lines.extend([
                "---",
                "",
                f"**Estimated Complexity:** {plan['estimated_complexity']}",
            ])

        return "\n".join(lines)
