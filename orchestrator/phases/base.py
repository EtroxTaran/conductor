"""Base phase class for workflow phases."""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Any

from ..utils.state import StateManager, PhaseStatus
from ..utils.logging import OrchestrationLogger
from ..utils.context import ContextManager, DriftResult
from ..agents import ClaudeAgent, CursorAgent, GeminiAgent


class BasePhase(ABC):
    """Base class for workflow phases."""

    phase_number: int = 0
    phase_name: str = "base"

    def __init__(
        self,
        project_dir: str | Path,
        state_manager: StateManager,
        logger: OrchestrationLogger,
    ):
        """Initialize the phase.

        Args:
            project_dir: Root directory of the project
            state_manager: State manager instance
            logger: Logger instance
        """
        self.project_dir = Path(project_dir)
        self.state = state_manager
        self.logger = logger
        self.phase_dir = self.state.get_phase_dir(self.phase_number)

        # Initialize agents
        self.claude = ClaudeAgent(project_dir)
        self.cursor = CursorAgent(project_dir)
        self.gemini = GeminiAgent(project_dir)

        # Initialize context manager
        self.context_manager = ContextManager(project_dir)

        # Configuration for drift handling
        self.warn_on_drift = True
        self.block_on_drift = False

    @abstractmethod
    def execute(self) -> dict:
        """Execute the phase.

        Returns:
            Dictionary with phase results
        """
        pass

    def run(self) -> dict:
        """Run the phase with state management.

        Returns:
            Dictionary with phase results
        """
        # Check for context drift before starting
        drift_result = self.check_context_drift()
        if drift_result.has_drift:
            self._handle_drift(drift_result)
            if self.block_on_drift:
                return {
                    "success": False,
                    "error": "Context drift detected; workflow blocked",
                    "drift": drift_result.to_dict(),
                }

        # Start phase
        self.state.start_phase(self.phase_number)
        self.logger.phase_start(self.phase_number, self.phase_name)

        try:
            result = self.execute()

            if result.get("success", False):
                self.state.complete_phase(self.phase_number, result)
                self.logger.phase_complete(self.phase_number, self.phase_name)
            else:
                error = result.get("error", "Unknown error")
                self.state.fail_phase(self.phase_number, error)
                self.logger.phase_failed(self.phase_number, self.phase_name, error)

            return result

        except Exception as e:
            error = str(e)
            self.state.fail_phase(self.phase_number, error)
            self.logger.phase_failed(self.phase_number, self.phase_name, error)
            return {"success": False, "error": error}

    def check_context_drift(self) -> DriftResult:
        """Check if context files have changed since workflow started.

        Returns:
            DriftResult with details about any changes
        """
        stored_context = self.state.get_context()
        if not stored_context:
            # No context captured yet - capture it now
            self.state.capture_context()
            return DriftResult(has_drift=False)

        from ..utils.context import ContextState
        stored_state = ContextState.from_dict(stored_context)
        return self.context_manager.validate_context(stored_state)

    def _handle_drift(self, drift_result: DriftResult) -> None:
        """Handle detected context drift.

        Args:
            drift_result: The drift detection result
        """
        summary = self.context_manager.get_drift_summary(drift_result)

        if self.warn_on_drift:
            self.logger.warning(
                f"Context drift detected in phase {self.phase_number}",
                phase=self.phase_number,
            )
            for file_key in drift_result.changed_files:
                self.logger.warning(f"  Modified: {file_key}", phase=self.phase_number)
            for file_key in drift_result.added_files:
                self.logger.warning(f"  Added: {file_key}", phase=self.phase_number)
            for file_key in drift_result.removed_files:
                self.logger.warning(f"  Removed: {file_key}", phase=self.phase_number)

    def sync_context(self) -> None:
        """Re-capture context state after handling drift."""
        self.state.sync_context()
        self.logger.info("Context re-synchronized", phase=self.phase_number)

    def read_file(self, path: Path) -> Optional[str]:
        """Read file content safely."""
        if path.exists():
            return path.read_text()
        return None

    def write_file(self, path: Path, content: Any) -> None:
        """Write content to file, creating directories if needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, (dict, list)):
            with open(path, "w") as f:
                json.dump(content, f, indent=2)
        else:
            path.write_text(str(content))

    def read_json(self, path: Path) -> Optional[dict]:
        """Read JSON file safely."""
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
        return None

    def get_product_spec(self) -> Optional[str]:
        """Read PRODUCT.md content."""
        return self.read_file(self.project_dir / "PRODUCT.md")

    def get_plan(self) -> Optional[dict]:
        """Read plan.json from planning phase."""
        plan_file = self.state.get_phase_dir(1) / "plan.json"
        return self.read_json(plan_file)

    def get_feedback(self) -> Optional[dict]:
        """Read consolidated feedback from validation phase."""
        feedback_file = self.state.get_phase_dir(2) / "consolidated-feedback.json"
        return self.read_json(feedback_file)

    def get_implementation_results(self) -> Optional[dict]:
        """Read implementation results from phase 3."""
        results_file = self.state.get_phase_dir(3) / "implementation-results.json"
        return self.read_json(results_file)
