# List Projects Skill

List all available projects in the meta-architect workspace.

## Overview

This skill scans the `projects/` directory and displays all initialized projects with their current status.

## Usage

```
/list-projects
```

## Output Format

```markdown
# Available Projects

| Project | Phase | Status | Last Updated |
|---------|-------|--------|--------------|
| my-feature | 3 - Implementation | 40% complete | 2026-01-22 |
| auth-system | 5 - Completion | Done | 2026-01-21 |
| api-refactor | 2 - Validation | Awaiting review | 2026-01-20 |

## Project Details

### my-feature
- **Path**: projects/my-feature/
- **Current Phase**: 3 - Implementation
- **Tasks**: 2/5 completed
- **Has PRODUCT.md**: Yes
- **Has Documents/**: Yes

### auth-system
- **Path**: projects/auth-system/
- **Current Phase**: 5 - Completion
- **Status**: Workflow complete
- **Has PRODUCT.md**: Yes

### api-refactor
- **Path**: projects/api-refactor/
- **Current Phase**: 2 - Validation
- **Status**: Awaiting Cursor/Gemini approval
- **Has PRODUCT.md**: Yes
```

## Discovery Logic

```bash
# Find all projects
ls -d projects/*/

# For each project, check:
# 1. Has .workflow/state.json?
# 2. Has PRODUCT.md?
# 3. Has Documents/?
```

## Project Validation

A valid project has:
- Directory exists in `projects/`
- Contains `PRODUCT.md` (required for workflow)
- May have `.workflow/` (created on first run)

## Status Indicators

| Status | Meaning |
|--------|---------|
| Not started | Has PRODUCT.md but no .workflow/ |
| In progress | Has active workflow state |
| Awaiting review | Waiting for agent approval |
| Blocked | Has errors or blockers |
| Done | Workflow completed successfully |

## Integration

Called by:
- User directly
- `/orchestrate` - To select a project
- Shell script: `./scripts/init.sh list`

## Example Discovery

```bash
# List project directories
for dir in projects/*/; do
    project_name=$(basename "$dir")

    # Check for state
    if [ -f "$dir/.workflow/state.json" ]; then
        state=$(cat "$dir/.workflow/state.json")
        phase=$(echo "$state" | jq -r '.current_phase')
        echo "$project_name: Phase $phase"
    elif [ -f "$dir/PRODUCT.md" ]; then
        echo "$project_name: Not started"
    else
        echo "$project_name: Missing PRODUCT.md"
    fi
done
```
