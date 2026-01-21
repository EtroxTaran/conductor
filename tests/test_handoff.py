"""Tests for Handoff component."""

import json
import pytest
import tempfile
from pathlib import Path

from orchestrator.utils.handoff import (
    HandoffBrief,
    HandoffGenerator,
    generate_handoff,
)
from orchestrator.utils.action_log import ActionLog, ActionType, reset_action_log
from orchestrator.utils.error_aggregator import ErrorAggregator, ErrorSource, ErrorSeverity, reset_error_aggregator


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory with workflow structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        workflow_dir = project_dir / ".workflow"
        workflow_dir.mkdir()
        (workflow_dir / "phases" / "planning").mkdir(parents=True)
        yield project_dir


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global instances before each test."""
    reset_action_log()
    reset_error_aggregator()
    yield
    reset_action_log()
    reset_error_aggregator()


class TestHandoffBrief:
    """Tests for HandoffBrief dataclass."""

    def test_to_dict(self):
        brief = HandoffBrief(
            generated_at="2024-01-15T10:00:00",
            project="test-project",
            current_phase=3,
            phase_status={"1": "completed", "2": "completed", "3": "in_progress"},
            current_task="T4",
            completed_tasks=["T1", "T2", "T3"],
            total_tasks=10,
            next_action="Continue implementing T4",
        )
        result = brief.to_dict()

        assert result["project"] == "test-project"
        assert result["current_phase"] == 3
        assert result["current_task"] == "T4"
        assert len(result["completed_tasks"]) == 3

    def test_from_dict(self):
        data = {
            "generated_at": "2024-01-15T10:00:00",
            "project": "test-project",
            "current_phase": 3,
            "phase_status": {"1": "completed", "2": "completed", "3": "in_progress"},
            "next_action": "Continue",
        }
        brief = HandoffBrief.from_dict(data)

        assert brief.project == "test-project"
        assert brief.current_phase == 3

    def test_to_markdown_basic(self):
        brief = HandoffBrief(
            generated_at="2024-01-15T10:00:00",
            project="test-project",
            current_phase=2,
            phase_status={"1": "completed", "2": "in_progress"},
            next_action="Continue validation",
        )
        md = brief.to_markdown()

        assert "# Handoff Brief: test-project" in md
        assert "**Phase:** 2/5" in md
        assert "Continue validation" in md

    def test_to_markdown_with_tasks(self):
        brief = HandoffBrief(
            generated_at="2024-01-15T10:00:00",
            project="test-project",
            current_phase=3,
            phase_status={},
            current_task="T4",
            completed_tasks=["T1", "T2", "T3"],
            total_tasks=10,
            next_action="Implement T4",
        )
        md = brief.to_markdown()

        assert "**Current Task:** T4" in md
        assert "3/10" in md  # Task progress

    def test_to_markdown_with_errors(self):
        brief = HandoffBrief(
            generated_at="2024-01-15T10:00:00",
            project="test-project",
            current_phase=3,
            phase_status={},
            unresolved_errors=[
                {"severity": "critical", "message": "Critical error", "phase": 3},
                {"severity": "error", "message": "Normal error"},
            ],
            next_action="Fix errors",
        )
        md = brief.to_markdown()

        assert "## Unresolved Errors" in md
        assert "Critical error" in md

    def test_to_markdown_with_blockers(self):
        brief = HandoffBrief(
            generated_at="2024-01-15T10:00:00",
            project="test-project",
            current_phase=3,
            phase_status={},
            blockers=["Missing API key", "Database down"],
            next_action="Resolve blockers",
        )
        md = brief.to_markdown()

        assert "## Blockers" in md
        assert "Missing API key" in md

    def test_to_markdown_with_recent_actions(self):
        brief = HandoffBrief(
            generated_at="2024-01-15T10:00:00",
            project="test-project",
            current_phase=3,
            phase_status={},
            last_actions=[
                {"timestamp": "2024-01-15T09:30:00", "agent": "claude", "phase": 3, "message": "Started task"},
                {"timestamp": "2024-01-15T09:35:00", "message": "Completed step"},
            ],
            next_action="Continue",
        )
        md = brief.to_markdown()

        assert "## Recent Actions" in md
        assert "[claude]" in md


class TestHandoffGenerator:
    """Tests for HandoffGenerator class."""

    def test_generate_empty_state(self, temp_project_dir):
        """Test generation with no state."""
        generator = HandoffGenerator(temp_project_dir)
        brief = generator.generate()

        assert brief.project == temp_project_dir.name
        assert brief.current_phase == 1
        assert brief.next_action != ""

    def test_generate_with_state(self, temp_project_dir):
        """Test generation with workflow state."""
        state = {
            "project_name": "test-project",
            "current_phase": 3,
            "phases": {
                "planning": {"status": "completed"},
                "validation": {"status": "completed"},
                "implementation": {"status": "in_progress"},
                "verification": {"status": "pending"},
                "completion": {"status": "pending"},
            },
            "created_at": "2024-01-15T08:00:00",
            "updated_at": "2024-01-15T10:00:00",
        }
        state_file = temp_project_dir / ".workflow" / "state.json"
        with open(state_file, "w") as f:
            json.dump(state, f)

        generator = HandoffGenerator(temp_project_dir)
        brief = generator.generate()

        assert brief.project == "test-project"
        assert brief.current_phase == 3
        assert brief.phase_status["1"] == "completed"
        assert brief.phase_status["3"] == "in_progress"

    def test_generate_with_tasks(self, temp_project_dir):
        """Test generation with task data."""
        tasks = {
            "tasks": [
                {"id": "T1", "title": "Task 1", "status": "completed"},
                {"id": "T2", "title": "Task 2", "status": "completed"},
                {"id": "T3", "title": "Task 3", "status": "in_progress",
                 "files_to_create": ["src/foo.py"], "files_to_modify": ["src/bar.py"]},
                {"id": "T4", "title": "Task 4", "status": "pending"},
            ]
        }
        tasks_file = temp_project_dir / ".workflow" / "phases" / "planning" / "tasks.json"
        with open(tasks_file, "w") as f:
            json.dump(tasks, f)

        generator = HandoffGenerator(temp_project_dir)
        brief = generator.generate()

        assert brief.current_task == "T3"
        assert len(brief.completed_tasks) == 2
        assert brief.total_tasks == 4
        assert "src/foo.py" in brief.files_in_progress

    def test_generate_with_actions(self, temp_project_dir):
        """Test generation includes recent actions."""
        workflow_dir = temp_project_dir / ".workflow"
        action_log = ActionLog(workflow_dir, console_output=False)

        action_log.log(ActionType.PHASE_START, "Started phase 3", phase=3)
        action_log.log(ActionType.AGENT_INVOKE, "Invoked Claude", agent="claude", phase=3)

        generator = HandoffGenerator(temp_project_dir)
        brief = generator.generate(include_actions=10)

        assert len(brief.last_actions) == 2

    def test_generate_with_errors(self, temp_project_dir):
        """Test generation includes unresolved errors."""
        workflow_dir = temp_project_dir / ".workflow"
        error_agg = ErrorAggregator(workflow_dir)

        error_agg.add_error(
            source=ErrorSource.EXCEPTION,
            error_type="TestError",
            message="Test error message",
            phase=3,
        )

        generator = HandoffGenerator(temp_project_dir)
        brief = generator.generate()

        assert len(brief.unresolved_errors) == 1
        assert brief.unresolved_errors[0]["message"] == "Test error message"

    def test_generate_next_action_critical_error(self, temp_project_dir):
        """Test next action prioritizes critical errors."""
        workflow_dir = temp_project_dir / ".workflow"
        error_agg = ErrorAggregator(workflow_dir)

        error_agg.add_error(
            source=ErrorSource.EXCEPTION,
            error_type="security_vulnerability",
            message="XSS detected",
            severity=ErrorSeverity.CRITICAL,
        )

        generator = HandoffGenerator(temp_project_dir)
        brief = generator.generate()

        assert "critical error" in brief.next_action.lower()

    def test_generate_next_action_failed_phase(self, temp_project_dir):
        """Test next action suggests retry on failed phase."""
        state = {
            "project_name": "test-project",
            "current_phase": 2,
            "phases": {
                "planning": {"status": "completed"},
                "validation": {"status": "failed", "error": "Score too low", "attempts": 1, "max_attempts": 3},
            },
        }
        state_file = temp_project_dir / ".workflow" / "state.json"
        with open(state_file, "w") as f:
            json.dump(state, f)

        generator = HandoffGenerator(temp_project_dir)
        brief = generator.generate()

        assert "retry" in brief.next_action.lower() or "phase 2" in brief.next_action.lower()

    def test_save(self, temp_project_dir):
        """Test saving handoff brief to files."""
        generator = HandoffGenerator(temp_project_dir)
        json_path, md_path = generator.save()

        assert json_path.exists()
        assert md_path.exists()

        # Check JSON content
        with open(json_path) as f:
            data = json.load(f)
            assert "project" in data
            assert "current_phase" in data

        # Check MD content
        with open(md_path) as f:
            content = f.read()
            assert "# Handoff Brief" in content

    def test_load(self, temp_project_dir):
        """Test loading saved handoff brief."""
        generator = HandoffGenerator(temp_project_dir)
        original = generator.generate()
        generator.save(original)

        loaded = generator.load()

        assert loaded is not None
        assert loaded.project == original.project
        assert loaded.current_phase == original.current_phase

    def test_load_nonexistent(self, temp_project_dir):
        """Test loading when no file exists."""
        generator = HandoffGenerator(temp_project_dir)
        loaded = generator.load()

        assert loaded is None


class TestGenerateHandoff:
    """Tests for generate_handoff helper function."""

    def test_generate_handoff_save_true(self, temp_project_dir):
        """Test generate_handoff with save=True."""
        brief = generate_handoff(temp_project_dir, save=True)

        assert brief is not None
        assert (temp_project_dir / ".workflow" / "handoff_brief.json").exists()
        assert (temp_project_dir / ".workflow" / "handoff_brief.md").exists()

    def test_generate_handoff_save_false(self, temp_project_dir):
        """Test generate_handoff with save=False."""
        brief = generate_handoff(temp_project_dir, save=False)

        assert brief is not None
        assert not (temp_project_dir / ".workflow" / "handoff_brief.json").exists()
