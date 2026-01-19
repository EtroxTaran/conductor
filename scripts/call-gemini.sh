#!/bin/bash
# call-gemini.sh - Invoke Gemini CLI for architecture review/validation
# Usage: call-gemini.sh <prompt-file> <output-file> [project-dir]
#
# This script is used by Claude Code to call Gemini for:
# - Plan validation (Phase 2)
# - Architecture verification (Phase 4)
#
# Default model: Gemini 3 Pro (latest as of Jan 2026)
# Can be overridden with GEMINI_MODEL environment variable

set -e

PROMPT_FILE="$1"
OUTPUT_FILE="$2"
PROJECT_DIR="${3:-.}"

# Model selection (Gemini 3 Pro is the latest, most capable model)
# Options: gemini-3-pro, gemini-3-flash, gemini-2.5-pro, gemini-2.5-flash
GEMINI_MODEL="${GEMINI_MODEL:-gemini-3-pro}"

# Validate arguments
if [ -z "$PROMPT_FILE" ] || [ -z "$OUTPUT_FILE" ]; then
    echo "Usage: call-gemini.sh <prompt-file> <output-file> [project-dir]"
    echo ""
    echo "Environment variables:"
    echo "  GEMINI_MODEL - Model to use (default: gemini-3-pro)"
    echo "                 Options: gemini-3-pro, gemini-3-flash, gemini-2.5-pro"
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
    echo '{"status": "error", "agent": "gemini", "message": "gemini CLI not found. Install with: npm install -g @google/gemini-cli"}' > "$OUTPUT_FILE"
    exit 1
fi

# Read prompt from file
PROMPT=$(cat "$PROMPT_FILE")

# Build context file options
# Gemini CLI reads GEMINI.md automatically, but we can also specify AGENTS.md
CONTEXT_OPTS=""
if [ -f "AGENTS.md" ]; then
    CONTEXT_OPTS="--read AGENTS.md"
fi

# Call Gemini CLI with JSON output
# Note: Gemini 3 Pro is the most capable model (released Dec 2025)
# - 1M+ token context window
# - Best reasoning and coding performance
# - Native tool use support
echo "Calling Gemini CLI with model: $GEMINI_MODEL"

gemini -m "$GEMINI_MODEL" \
    -p "$PROMPT" \
    --output-format json \
    $CONTEXT_OPTS \
    > "$OUTPUT_FILE" 2>&1

# Check if output was created
if [ ! -f "$OUTPUT_FILE" ]; then
    echo '{"status": "error", "agent": "gemini", "message": "Failed to create output file"}' > "$OUTPUT_FILE"
    exit 1
fi

# Validate JSON output
if ! python3 -c "import json; json.load(open('$OUTPUT_FILE'))" 2>/dev/null; then
    # If not valid JSON, wrap the output
    CONTENT=$(cat "$OUTPUT_FILE")
    echo "{\"status\": \"completed\", \"agent\": \"gemini\", \"raw_output\": $(echo "$CONTENT" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')}" > "$OUTPUT_FILE"
fi

echo "Gemini review complete. Output saved to: $OUTPUT_FILE"
