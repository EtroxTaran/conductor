#!/bin/bash
# Orchestration wrapper script
# Usage: ./orchestrate.sh [args]
#
# This script can be run from any directory and will use the current directory
# as the project directory.
#
# Examples:
#   ./orchestrate.sh --start          # Start workflow
#   ./orchestrate.sh --resume         # Resume from last phase
#   ./orchestrate.sh --status         # Check status
#   ./orchestrate.sh --reset          # Reset workflow
#   ./orchestrate.sh --phase 3        # Start from phase 3

set -e

# Get the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
META_ARCHITECT_DIR="$(dirname "$SCRIPT_DIR")"

# Add orchestrator to Python path
export PYTHONPATH="$META_ARCHITECT_DIR:$PYTHONPATH"

# Run the orchestrator module
python3 -m orchestrator "$@"
