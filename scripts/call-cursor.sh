#!/bin/bash
# call-cursor.sh - Invoke Cursor CLI for code review/validation
# Usage: call-cursor.sh <prompt-file> <output-file> [project-dir]
#
# This script is used by Claude Code to call Cursor for:
# - Plan validation (Phase 2)
# - Code verification (Phase 4)

set -e

PROMPT_FILE="$1"
OUTPUT_FILE="$2"
PROJECT_DIR="${3:-.}"

# Validate arguments
if [ -z "$PROMPT_FILE" ] || [ -z "$OUTPUT_FILE" ]; then
    echo "Usage: call-cursor.sh <prompt-file> <output-file> [project-dir]"
    exit 1
fi

if [ ! -f "$PROMPT_FILE" ]; then
    echo "Error: Prompt file not found: $PROMPT_FILE"
    exit 1
fi

# Change to project directory
cd "$PROJECT_DIR"

# Check if cursor-agent is available
if ! command -v cursor-agent &> /dev/null; then
    echo '{"status": "error", "agent": "cursor", "message": "cursor-agent CLI not found. Please install it."}' > "$OUTPUT_FILE"
    exit 1
fi

# Read prompt from file
PROMPT=$(cat "$PROMPT_FILE")

# Call Cursor CLI with JSON output
# Note: cursor-agent reads .cursor/rules automatically
cursor-agent -p "$PROMPT" \
    --output-format json \
    --force \
    > "$OUTPUT_FILE" 2>&1

# Check if output was created
if [ ! -f "$OUTPUT_FILE" ]; then
    echo '{"status": "error", "agent": "cursor", "message": "Failed to create output file"}' > "$OUTPUT_FILE"
    exit 1
fi

echo "Cursor review complete. Output saved to: $OUTPUT_FILE"
