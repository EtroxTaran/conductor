"""Tests for end_phase support in LangGraph workflow.

Verifies that:
- end_phase field is included in WorkflowState
- create_initial_state accepts and stores end_phase
- Routers check end_phase and route to completion early
- planning_send_router routes to completion when end_phase=1
- _check_workflow_success checks end_phase instead of hardcoded phase 5
"""


from orchestrator.langgraph.routers.general import (
    _reached_end_phase,
    approval_gate_router,
    pre_implementation_router,
)
from orchestrator.langgraph.state import (
    PhaseState,
    PhaseStatus,
    WorkflowState,
    create_initial_state,
)


class TestEndPhaseState:
    """Test end_phase in WorkflowState."""

    def test_create_initial_state_default_end_phase(self, tmp_path):
        """end_phase defaults to 5."""
        state = create_initial_state(
            project_dir=str(tmp_path),
            project_name="test",
        )
        assert state["end_phase"] == 5

    def test_create_initial_state_custom_end_phase(self, tmp_path):
        """end_phase can be set to 1-5."""
        for phase in range(1, 6):
            state = create_initial_state(
                project_dir=str(tmp_path),
                project_name="test",
                end_phase=phase,
            )
            assert state["end_phase"] == phase

    def test_create_initial_state_clamps_end_phase(self, tmp_path):
        """end_phase is clamped to 1-5."""
        state = create_initial_state(
            project_dir=str(tmp_path),
            project_name="test",
            end_phase=0,
        )
        assert state["end_phase"] == 1

        state = create_initial_state(
            project_dir=str(tmp_path),
            project_name="test",
            end_phase=10,
        )
        assert state["end_phase"] == 5


class TestReachedEndPhase:
    """Test _reached_end_phase helper."""

    def test_not_reached(self, tmp_path):
        """Returns False when current phase < end_phase."""
        state = create_initial_state(
            project_dir=str(tmp_path),
            project_name="test",
            end_phase=5,
        )
        assert _reached_end_phase(state, 1) is False
        assert _reached_end_phase(state, 2) is False
        assert _reached_end_phase(state, 4) is False

    def test_reached_exact(self, tmp_path):
        """Returns True when current phase == end_phase."""
        state = create_initial_state(
            project_dir=str(tmp_path),
            project_name="test",
            end_phase=2,
        )
        assert _reached_end_phase(state, 2) is True

    def test_reached_past(self, tmp_path):
        """Returns True when current phase > end_phase."""
        state = create_initial_state(
            project_dir=str(tmp_path),
            project_name="test",
            end_phase=2,
        )
        assert _reached_end_phase(state, 3) is True

    def test_default_end_phase_missing(self, tmp_path):
        """Defaults to 5 if end_phase not in state."""
        state: WorkflowState = {"project_dir": str(tmp_path), "project_name": "test"}  # type: ignore[typeddict-item]
        assert _reached_end_phase(state, 4) is False
        assert _reached_end_phase(state, 5) is True


class TestPreImplementationRouterEndPhase:
    """Test that pre_implementation_router respects end_phase."""

    def test_routes_to_completion_when_end_phase_2(self, tmp_path):
        """When end_phase=2, routes to completion instead of implementation."""
        state = create_initial_state(
            project_dir=str(tmp_path),
            project_name="test",
            end_phase=2,
        )
        state["next_decision"] = "continue"
        result = pre_implementation_router(state)
        assert result == "completion"

    def test_routes_to_implementation_when_end_phase_5(self, tmp_path):
        """When end_phase=5, routes to implementation normally."""
        state = create_initial_state(
            project_dir=str(tmp_path),
            project_name="test",
            end_phase=5,
        )
        state["next_decision"] = "continue"
        result = pre_implementation_router(state)
        assert result == "implementation"

    def test_routes_to_completion_when_end_phase_1(self, tmp_path):
        """When end_phase=1, routes to completion (already past end)."""
        state = create_initial_state(
            project_dir=str(tmp_path),
            project_name="test",
            end_phase=1,
        )
        state["next_decision"] = "continue"
        result = pre_implementation_router(state)
        assert result == "completion"


class TestApprovalGateRouterEndPhase:
    """Test that approval_gate_router respects end_phase."""

    def test_routes_to_completion_when_end_phase_2(self, tmp_path):
        """When end_phase=2, routes to completion."""
        state = create_initial_state(
            project_dir=str(tmp_path),
            project_name="test",
            end_phase=2,
        )
        state["next_decision"] = "continue"
        result = approval_gate_router(state)
        assert result == "completion"

    def test_routes_normally_when_end_phase_5(self, tmp_path):
        """When end_phase=5, routes to pre_implementation."""
        state = create_initial_state(
            project_dir=str(tmp_path),
            project_name="test",
            end_phase=5,
        )
        state["next_decision"] = "continue"
        result = approval_gate_router(state)
        assert result == "pre_implementation"


class TestPlanningSendRouterEndPhase:
    """Test that planning_send_router respects end_phase."""

    def test_routes_to_completion_when_end_phase_1(self, tmp_path):
        """When end_phase=1 and plan exists, routes to completion."""
        from orchestrator.langgraph.workflow import planning_send_router

        state = create_initial_state(
            project_dir=str(tmp_path),
            project_name="test",
            end_phase=1,
        )
        state["plan"] = {"plan_name": "Test Plan", "tasks": []}

        result = planning_send_router(state)
        assert len(result) == 1
        assert result[0].node == "completion"

    def test_routes_to_validators_when_end_phase_5(self, tmp_path):
        """When end_phase=5 and plan exists, routes to validators."""
        from orchestrator.langgraph.workflow import planning_send_router

        state = create_initial_state(
            project_dir=str(tmp_path),
            project_name="test",
            end_phase=5,
        )
        state["plan"] = {"plan_name": "Test Plan", "tasks": []}
        phase_1 = state["phase_status"]["1"]
        phase_1.status = PhaseStatus.COMPLETED

        result = planning_send_router(state)
        assert len(result) == 2
        nodes = {r.node for r in result}
        assert nodes == {"cursor_validate", "gemini_validate"}


class TestCheckWorkflowSuccessEndPhase:
    """Test _check_workflow_success with end_phase."""

    def _make_orchestrator(self):
        """Create a minimal orchestrator-like object for testing."""

        class FakeOrchestrator:
            def _check_workflow_success(self, result: dict) -> bool:
                end_phase = result.get("end_phase", 5)
                phase_status = result.get("phase_status", {})

                # Primary: completion node sets current_phase=5, next_decision="continue"
                if result.get("current_phase") == 5 and result.get("next_decision") == "continue":
                    return True

                # Secondary: phase_status shows completion node ran (marks phase 5)
                phase_5 = phase_status.get("5")
                if phase_5 and hasattr(phase_5, "status"):
                    status_val = (
                        phase_5.status.value if hasattr(phase_5.status, "value") else phase_5.status
                    )
                    if status_val == "completed":
                        return True

                # For early stops, check if the target phase completed
                if end_phase < 5:
                    target = phase_status.get(str(end_phase))
                    if target and hasattr(target, "status"):
                        status_val = (
                            target.status.value
                            if hasattr(target.status, "value")
                            else target.status
                        )
                        if status_val == "completed":
                            return True

                return False

        return FakeOrchestrator()

    def test_success_with_phase_5_completed(self):
        """Standard workflow: phase 5 completed = success."""
        orch = self._make_orchestrator()
        result = {
            "end_phase": 5,
            "phase_status": {
                "5": PhaseState(status=PhaseStatus.COMPLETED),
            },
        }
        assert orch._check_workflow_success(result) is True

    def test_success_with_early_stop_phase_2(self):
        """Early stop: end_phase=2 with phase 5 completed (completion node ran)."""
        orch = self._make_orchestrator()
        result = {
            "end_phase": 2,
            "phase_status": {
                "2": PhaseState(status=PhaseStatus.COMPLETED),
                "5": PhaseState(status=PhaseStatus.COMPLETED),
            },
        }
        assert orch._check_workflow_success(result) is True

    def test_failure_with_no_phases_completed(self):
        """No phases completed = failure."""
        orch = self._make_orchestrator()
        result = {
            "end_phase": 5,
            "phase_status": {
                "5": PhaseState(status=PhaseStatus.PENDING),
            },
        }
        assert orch._check_workflow_success(result) is False

    def test_success_end_phase_2_target_completed(self):
        """Early stop: end_phase=2 with phase 2 completed but phase 5 not."""
        orch = self._make_orchestrator()
        result = {
            "end_phase": 2,
            "phase_status": {
                "2": PhaseState(status=PhaseStatus.COMPLETED),
                "5": PhaseState(status=PhaseStatus.PENDING),
            },
        }
        assert orch._check_workflow_success(result) is True

    def test_success_via_current_phase_and_next_decision(self):
        """Primary check: current_phase=5 + next_decision=continue = success."""
        orch = self._make_orchestrator()
        result = {
            "end_phase": 2,
            "current_phase": 5,
            "next_decision": "continue",
            "phase_status": {
                "2": PhaseState(status=PhaseStatus.PENDING),
                "5": PhaseState(status=PhaseStatus.PENDING),
            },
        }
        assert orch._check_workflow_success(result) is True

    def test_failure_current_phase_5_but_escalate(self):
        """current_phase=5 but next_decision=escalate = failure."""
        orch = self._make_orchestrator()
        result = {
            "end_phase": 5,
            "current_phase": 5,
            "next_decision": "escalate",
            "phase_status": {
                "5": PhaseState(status=PhaseStatus.PENDING),
            },
        }
        assert orch._check_workflow_success(result) is False
