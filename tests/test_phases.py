"""Tests for workflow phases."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from orchestrator.phases.phase1_planning import PlanningPhase
from orchestrator.phases.phase2_validation import ValidationPhase
from orchestrator.phases.phase3_implementation import ImplementationPhase
from orchestrator.phases.phase4_verification import VerificationPhase
from orchestrator.phases.phase5_completion import CompletionPhase
from orchestrator.utils.state import PhaseStatus


class TestPlanningPhase:
    """Tests for Phase 1: Planning."""

    def test_execute_missing_product_md(self, temp_project_dir, state_manager, logger):
        """Test execution fails without PRODUCT.md."""
        # Remove PRODUCT.md
        (temp_project_dir / "PRODUCT.md").unlink()

        phase = PlanningPhase(temp_project_dir, state_manager, logger)
        result = phase.execute()

        assert result["success"] is False
        assert "PRODUCT.md not found" in result["error"]

    @patch.object(PlanningPhase, "claude")
    def test_execute_success(
        self, mock_claude, temp_project_dir, state_manager, logger, mock_claude_agent
    ):
        """Test successful planning execution."""
        # Setup mock
        mock_claude_agent.run_planning.return_value.success = True
        mock_claude_agent.run_planning.return_value.parsed_output = {
            "plan_name": "Test",
            "summary": "Test plan",
            "phases": [{"phase": 1, "name": "Setup", "tasks": []}],
            "test_strategy": {},
            "estimated_complexity": "low",
        }
        mock_claude.run_planning = mock_claude_agent.run_planning

        phase = PlanningPhase(temp_project_dir, state_manager, logger)
        phase.claude = mock_claude_agent

        result = phase.execute()

        assert result["success"] is True
        assert "plan" in result
        assert (state_manager.get_phase_dir(1) / "plan.json").exists()
        assert (state_manager.get_phase_dir(1) / "PLAN.md").exists()

    def test_validate_plan_missing_fields(self, temp_project_dir, state_manager, logger):
        """Test plan validation catches missing fields."""
        phase = PlanningPhase(temp_project_dir, state_manager, logger)

        errors = phase._validate_plan({})
        assert len(errors) > 0
        assert any("plan_name" in e for e in errors)

    def test_validate_plan_empty_phases(self, temp_project_dir, state_manager, logger):
        """Test plan validation catches empty phases."""
        phase = PlanningPhase(temp_project_dir, state_manager, logger)

        errors = phase._validate_plan({
            "plan_name": "Test",
            "summary": "Test",
            "phases": [],
        })
        assert any("no phases" in e for e in errors)

    def test_generate_plan_markdown(self, temp_project_dir, state_manager, logger, sample_plan):
        """Test markdown generation from plan."""
        phase = PlanningPhase(temp_project_dir, state_manager, logger)
        md = phase._generate_plan_markdown(sample_plan)

        assert "# Implementation Plan" in md
        assert sample_plan["plan_name"] in md
        assert sample_plan["summary"] in md
        assert "T1" in md


class TestValidationPhase:
    """Tests for Phase 2: Validation."""

    def test_execute_missing_plan(self, temp_project_dir, state_manager, logger):
        """Test execution fails without plan.json."""
        phase = ValidationPhase(temp_project_dir, state_manager, logger)
        result = phase.execute()

        assert result["success"] is False
        assert "plan.json not found" in result["error"]

    def test_consolidate_feedback(self, temp_project_dir, state_manager, logger):
        """Test feedback consolidation."""
        phase = ValidationPhase(temp_project_dir, state_manager, logger)

        cursor_feedback = {
            "reviewer": "cursor",
            "overall_assessment": "approve",
            "score": 8,
            "concerns": [
                {"severity": "low", "area": "style", "description": "Minor style issue"}
            ],
            "strengths": ["Good structure"],
        }
        gemini_feedback = {
            "reviewer": "gemini",
            "overall_assessment": "approve",
            "score": 9,
            "architecture_review": {
                "concerns": [
                    {"area": "scaling", "description": "Consider caching"}
                ],
            },
        }

        consolidated = phase._consolidate_feedback(cursor_feedback, gemini_feedback)

        assert consolidated["recommendation"] == "proceed"
        assert len(consolidated["all_concerns"]) == 2
        assert len(consolidated["all_strengths"]) == 1

    def test_check_approval_both_approve(self, temp_project_dir, state_manager, logger):
        """Test approval when both validators approve."""
        phase = ValidationPhase(temp_project_dir, state_manager, logger)

        consolidated = {
            "recommendation": "proceed",
            "blocking_issues": [],
        }
        assert phase._check_approval(consolidated) is True

    def test_check_approval_blocking_issues(self, temp_project_dir, state_manager, logger):
        """Test approval blocked by issues."""
        phase = ValidationPhase(temp_project_dir, state_manager, logger)

        consolidated = {
            "recommendation": "proceed",
            "blocking_issues": [{"description": "Critical issue"}],
        }
        assert phase._check_approval(consolidated) is False


class TestImplementationPhase:
    """Tests for Phase 3: Implementation."""

    def test_execute_missing_plan(self, temp_project_dir, state_manager, logger):
        """Test execution fails without plan."""
        phase = ImplementationPhase(temp_project_dir, state_manager, logger)
        result = phase.execute()

        assert result["success"] is False
        assert "plan.json not found" in result["error"]

    def test_detect_test_commands_npm(self, temp_project_dir, state_manager, logger):
        """Test detection of npm test command."""
        # Create package.json
        package_json = temp_project_dir / "package.json"
        package_json.write_text(json.dumps({
            "scripts": {"test": "jest"}
        }))

        phase = ImplementationPhase(temp_project_dir, state_manager, logger)
        commands = phase._detect_test_commands()

        assert "npm test" in commands

    def test_detect_test_commands_pytest(self, temp_project_dir, state_manager, logger):
        """Test detection of pytest command."""
        # Create tests directory
        (temp_project_dir / "tests").mkdir()

        phase = ImplementationPhase(temp_project_dir, state_manager, logger)
        commands = phase._detect_test_commands()

        assert "pytest" in commands

    def test_parse_test_counts_pytest(self, temp_project_dir, state_manager, logger):
        """Test parsing pytest output."""
        phase = ImplementationPhase(temp_project_dir, state_manager, logger)

        output = "===== 5 passed, 2 failed, 1 skipped ====="
        counts = phase._parse_test_counts(output)

        assert counts["passed"] == 5
        assert counts["failed"] == 2
        assert counts["skipped"] == 1


class TestVerificationPhase:
    """Tests for Phase 4: Verification."""

    def test_combine_verification(self, temp_project_dir, state_manager, logger):
        """Test verification result combination."""
        phase = VerificationPhase(temp_project_dir, state_manager, logger)

        cursor_review = {
            "reviewer": "cursor",
            "approved": True,
            "overall_code_quality": 8,
            "blocking_issues": [],
            "files_reviewed": [
                {
                    "file": "test.py",
                    "status": "approved",
                    "issues": [
                        {"severity": "warning", "type": "style", "description": "Minor issue"}
                    ],
                }
            ],
        }
        gemini_review = {
            "reviewer": "gemini",
            "approved": True,
            "architecture_assessment": {"modularity_score": 9},
            "blocking_issues": [],
            "technical_debt": {"items": []},
        }

        verification = phase._combine_verification(cursor_review, gemini_review)

        assert verification["code_quality_score"] == 8
        assert verification["architecture_score"] == 9
        assert len(verification["blocking_issues"]) == 0
        assert len(verification["warnings"]) == 1

    def test_check_approval(self, temp_project_dir, state_manager, logger):
        """Test approval checking."""
        phase = VerificationPhase(temp_project_dir, state_manager, logger)

        # Both approve
        assert phase._check_approval(
            {"approved": True},
            {"approved": True}
        ) is True

        # One rejects
        assert phase._check_approval(
            {"approved": True},
            {"approved": False}
        ) is False


class TestCompletionPhase:
    """Tests for Phase 5: Completion."""

    def test_generate_next_steps(self, temp_project_dir, state_manager, logger):
        """Test next steps generation."""
        phase = CompletionPhase(temp_project_dir, state_manager, logger)

        verification = {
            "blocking_issues": [],
            "warnings": [{"description": "Minor warning"}],
        }

        steps = phase._generate_next_steps(verification)

        assert len(steps) > 0
        assert any("test" in s.lower() for s in steps)

    def test_generate_next_steps_with_blocking(self, temp_project_dir, state_manager, logger):
        """Test next steps with blocking issues."""
        phase = CompletionPhase(temp_project_dir, state_manager, logger)

        verification = {
            "blocking_issues": [
                {"description": "Critical security issue"}
            ],
            "warnings": [],
        }

        steps = phase._generate_next_steps(verification)

        assert any("blocking" in s.lower() or "critical" in s.lower() for s in steps)
