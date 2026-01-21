---
description: Check for available meta-architect updates for a project
allowed-tools: ["Read", "Bash"]
---

# Check Project Updates

Check if a project has available meta-architect template updates.

## Arguments

- `--project <name>` - Project name to check (required unless in project directory)
- `--all` - Check all projects
- `--json` - Output as JSON

## Instructions

1. Determine the project to check:
   - Use `--project <name>` if provided
   - Or use current directory if inside a project

2. Run the update check:

```bash
python -m orchestrator --project <project-name> --check-updates
```

Or for all projects:

```bash
python -m orchestrator --check-all-updates
```

3. Display the results showing:
   - Current version vs latest version
   - Whether updates are available
   - If it's a breaking update (major version change)
   - Changelog entries since current version
   - Files that would be updated

## Output Format

```
Update Check: <project-name>
--------------------------------------------------
  Current version:  0.1.0
  Latest version:   0.2.0
  Status:           Updates available

  Changes since 0.1.0:
  [0.2.0] 2026-01-21
    - Added project update mechanism
    - Added observability system
    - Added Ralph Wiggum loop

  Files that would be updated:
    - CLAUDE.md
    - GEMINI.md
    - .cursor/rules

  Run '/update-project <project-name>' to apply updates.
```

## Usage Examples

```
/check-updates --project my-app
/check-updates --all
/check-updates --project my-app --json
```

## Related Commands

- `/update-project` - Apply available updates
- `/sync-projects` - Sync templates to all projects
