"""Agent wrappers for CLI tools.

This module provides wrappers for various CLI agents used in the orchestrator:
- ClaudeAgent: Wrapper for Claude Code CLI with enhanced features
- CursorAgent: Wrapper for Cursor CLI
- GeminiAgent: Wrapper for Gemini CLI

Enhanced features available across agents:
- Session continuity for iterative refinement
- Audit trail for debugging and compliance
- Error context preservation for intelligent retries
- Budget control for cost management
- Unified adapter layer for loop execution
"""

from .base import BaseAgent, AgentResult
from .claude_agent import ClaudeAgent
from .cursor_agent import CursorAgent
from .gemini_agent import GeminiAgent
from .session_manager import SessionManager, SessionInfo
from .error_context import ErrorContextManager, ErrorContext, ErrorType
from .budget import (
    BudgetManager,
    BudgetConfig,
    BudgetExceeded,
    BudgetEnforcementResult,
    SpendRecord,
    AGENT_PRICING,
    get_model_pricing,
)
from .adapter import (
    AgentType,
    AgentAdapter,
    AgentCapabilities,
    IterationResult,
    ClaudeAdapter,
    CursorAdapter,
    GeminiAdapter,
    create_adapter,
    get_agent_capabilities,
    get_available_agents,
    get_agent_for_task,
)

__all__ = [
    # Base classes
    "BaseAgent",
    "AgentResult",
    # Agent implementations
    "ClaudeAgent",
    "CursorAgent",
    "GeminiAgent",
    # Session management
    "SessionManager",
    "SessionInfo",
    # Error handling
    "ErrorContextManager",
    "ErrorContext",
    "ErrorType",
    # Budget control
    "BudgetManager",
    "BudgetConfig",
    "BudgetExceeded",
    "BudgetEnforcementResult",
    "SpendRecord",
    "AGENT_PRICING",
    "get_model_pricing",
    # Adapter layer
    "AgentType",
    "AgentAdapter",
    "AgentCapabilities",
    "IterationResult",
    "ClaudeAdapter",
    "CursorAdapter",
    "GeminiAdapter",
    "create_adapter",
    "get_agent_capabilities",
    "get_available_agents",
    "get_agent_for_task",
]
