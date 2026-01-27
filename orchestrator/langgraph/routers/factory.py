"""Router factory for reducing boilerplate in workflow routers.

Most routers follow a common pattern of checking next_decision and routing
based on CONTINUE/RETRY/ESCALATE/ABORT. This factory creates routers that
follow this pattern while allowing custom fallback logic.

Usage:
    # Simple router with standard routing
    my_router = create_decision_router(
        continue_route="next_node",
        retry_route="previous_node",  # Optional
        default_route="next_node",
    )

    # Router with custom fallback logic
    my_router = create_decision_router(
        continue_route="next_node",
        default_route="next_node",
        fallback_fn=lambda state: "custom" if state.get("flag") else "default",
    )
"""

import logging
from collections.abc import Callable
from typing import Optional, TypeVar

from ..state import WorkflowDecision, WorkflowState

logger = logging.getLogger(__name__)

# Type for route names
RouteType = TypeVar("RouteType", bound=str)


class RouterConfig:
    """Configuration for a decision-based router.

    Attributes:
        continue_route: Route when decision is CONTINUE
        retry_route: Route when decision is RETRY (optional)
        escalate_route: Route when decision is ESCALATE (default: "human_escalation")
        abort_route: Route when decision is ABORT (default: "__end__")
        default_route: Default route when no decision matches
        fallback_fn: Optional function for custom fallback logic
    """

    def __init__(
        self,
        continue_route: str,
        default_route: str,
        retry_route: Optional[str] = None,
        escalate_route: str = "human_escalation",
        abort_route: str = "__end__",
        fallback_fn: Optional[Callable[[WorkflowState], str]] = None,
    ):
        self.continue_route = continue_route
        self.retry_route = retry_route
        self.escalate_route = escalate_route
        self.abort_route = abort_route
        self.default_route = default_route
        self.fallback_fn = fallback_fn


def create_decision_router(
    continue_route: str,
    default_route: str,
    retry_route: Optional[str] = None,
    escalate_route: str = "human_escalation",
    abort_route: str = "__end__",
    fallback_fn: Optional[Callable[[WorkflowState], str]] = None,
    name: Optional[str] = None,
) -> Callable[[WorkflowState], str]:
    """Create a router that routes based on next_decision.

    This factory creates routers that follow the standard pattern:
    1. Check next_decision for CONTINUE/RETRY/ESCALATE/ABORT
    2. Route accordingly
    3. Fall back to custom logic or default route

    Args:
        continue_route: Route when decision is CONTINUE
        default_route: Default route when no decision matches
        retry_route: Route when decision is RETRY (optional)
        escalate_route: Route when decision is ESCALATE
        abort_route: Route when decision is ABORT
        fallback_fn: Optional function for custom fallback logic
        name: Optional name for logging/debugging

    Returns:
        Router function that takes state and returns route name

    Example:
        # Simple router
        router = create_decision_router(
            continue_route="next_phase",
            default_route="next_phase",
        )

        # Router with retry support
        router = create_decision_router(
            continue_route="verification",
            retry_route="implementation",
            default_route="verification",
        )

        # Router with custom fallback
        router = create_decision_router(
            continue_route="planning",
            default_route="planning",
            fallback_fn=lambda s: "escalate" if s.get("errors") else "planning",
        )
    """
    router_name = name or f"router({continue_route})"

    def router(state: WorkflowState) -> str:
        """Route based on next_decision."""
        decision = state.get("next_decision")

        # Standard decision routing
        if decision == WorkflowDecision.CONTINUE or decision == "continue":
            logger.debug(f"{router_name}: CONTINUE -> {continue_route}")
            return continue_route

        if retry_route and (decision == WorkflowDecision.RETRY or decision == "retry"):
            logger.debug(f"{router_name}: RETRY -> {retry_route}")
            return retry_route

        if decision == WorkflowDecision.ESCALATE or decision == "escalate":
            logger.debug(f"{router_name}: ESCALATE -> {escalate_route}")
            return escalate_route

        if decision == WorkflowDecision.ABORT or decision == "abort":
            logger.debug(f"{router_name}: ABORT -> {abort_route}")
            return abort_route

        # Custom fallback logic
        if fallback_fn:
            route = fallback_fn(state)
            logger.debug(f"{router_name}: fallback -> {route}")
            return route

        # Default route
        logger.debug(f"{router_name}: default -> {default_route}")
        return default_route

    # Preserve function metadata for debugging
    router.__name__ = router_name
    router.__doc__ = f"Decision router: CONTINUE->{continue_route}, default->{default_route}"

    return router


def create_phase_router(
    success_route: str,
    retry_route: str,
    phase_key: Optional[str] = None,
    result_key: Optional[str] = None,
    max_attempts: int = 3,
) -> Callable[[WorkflowState], str]:
    """Create a router that checks phase status and result for routing.

    This factory creates routers that:
    1. Check next_decision first
    2. Check phase status (if phase_key provided)
    3. Check result (if result_key provided)
    4. Fall back to success_route

    Args:
        success_route: Route when phase/check passes
        retry_route: Route when phase/check fails (retryable)
        phase_key: Key in phase_status to check (e.g., "1", "3")
        result_key: Key in state to check for success (e.g., "implementation_result")
        max_attempts: Max attempts before escalation

    Returns:
        Router function
    """

    def fallback_logic(state: WorkflowState) -> str:
        # Check phase status if key provided
        if phase_key:
            phase_status = state.get("phase_status", {})
            phase = phase_status.get(phase_key)

            if phase and hasattr(phase, "status"):
                from ..state import PhaseStatus

                if phase.status == PhaseStatus.COMPLETED:
                    return success_route
                elif phase.status == PhaseStatus.FAILED:
                    if phase.attempts >= max_attempts:
                        return "human_escalation"
                    return retry_route

        # Check result if key provided
        if result_key:
            result = state.get(result_key, {})
            if isinstance(result, dict):
                if result.get("success"):
                    return success_route
                if result.get("failed"):
                    return retry_route

        return success_route

    return create_decision_router(
        continue_route=success_route,
        retry_route=retry_route,
        default_route=success_route,
        fallback_fn=fallback_logic,
    )


def create_check_router(
    success_route: str,
    retry_route: str,
    result_key: str,
    blocking_field: str = "blocking_issues",
) -> Callable[[WorkflowState], str]:
    """Create a router for verification/check nodes.

    Routes based on a result dict in state with optional blocking issues check.

    Args:
        success_route: Route when check passes
        retry_route: Route when check fails (retryable)
        result_key: Key in state containing check result
        blocking_field: Field in result dict for blocking issues

    Returns:
        Router function
    """

    def fallback_logic(state: WorkflowState) -> str:
        result = state.get(result_key, {})
        if not isinstance(result, dict):
            return success_route

        # Check if passed
        if result.get("passed"):
            return success_route

        # Check for blocking issues
        blocking = result.get(blocking_field, [])
        if blocking:
            return "human_escalation"

        # Non-blocking failure - continue
        return success_route

    return create_decision_router(
        continue_route=success_route,
        retry_route=retry_route,
        default_route=success_route,
        fallback_fn=fallback_logic,
    )


# Pre-built router factories for common patterns


def simple_continue_router(success_route: str) -> Callable[[WorkflowState], str]:
    """Create a router that only handles CONTINUE and ESCALATE/ABORT.

    For nodes that don't support RETRY.

    Args:
        success_route: Route for CONTINUE

    Returns:
        Router function
    """
    return create_decision_router(
        continue_route=success_route,
        default_route=success_route,
    )


def verification_router(
    success_route: str,
    retry_route: str,
) -> Callable[[WorkflowState], str]:
    """Create a router for verification/review nodes.

    Handles CONTINUE, RETRY, ESCALATE, ABORT.

    Args:
        success_route: Route when verification passes
        retry_route: Route when verification fails

    Returns:
        Router function
    """
    return create_decision_router(
        continue_route=success_route,
        retry_route=retry_route,
        default_route=success_route,
    )
