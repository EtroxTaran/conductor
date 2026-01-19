#!/bin/bash
# call-gemini.sh - Invoke Gemini CLI for architecture review/validation
# Usage: call-gemini.sh <prompt-file> <output-file> [project-dir]
#
# This script is used by Claude Code to call Gemini for:
# - Plan validation (Phase 2)
# - Architecture verification (Phase 4)

set -e

PROMPT_FILE="$1"
OUTPUT_FILE="$2"
PROJECT_DIR="${3:-.}"

# Validate arguments
if [ -z "$PROMPT_FILE" ] || [ -z "$OUTPUT_FILE" ]; then
    echo "Usage: call-gemini.sh <prompt-file> <output-file> [project-dir]"
    exit 1
fi

if [ ! -f "$PROMPT_FILE" ]; then
    echo "Error: Prompt file not found: $PROMPT_FILE"
    exit 1
fi

# Change to project directory
cd "$PROJECT_DIR"

# Check if gemini CLI is available
if ! command -v gemini &> /dev/null; then
    echo '{"status": "error", "agent": "gemini", "message": "gemini CLI not found. Please install it."}' > "$OUTPUT_FILE"
    exit 1
fi

# Read prompt from file
PROMPT=$(cat "$PROMPT_FILE")

# Call Gemini CLI with JSON output
# Note: gemini reads GEMINI.md automatically from the project root
gemini -p "$PROMPT" \
    --output-format json \
    > "$OUTPUT_FILE" 2>&1

# Check if output was created
if [ ! -f "$OUTPUT_FILE" ]; then
    echo '{"status": "error", "agent": "gemini", "message": "Failed to create output file"}' > "$OUTPUT_FILE"
    exit 1
fi

echo "Gemini review complete. Output saved to: $OUTPUT_FILE"
