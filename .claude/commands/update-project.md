---
description: Apply available meta-architect updates to a project
allowed-tools: ["Read", "Bash"]
---

# Update Project

Apply available meta-architect template updates to a project.

## Arguments

- `--project <name>` - Project name to update (required unless in project directory)
- `--dry-run` - Show what would be changed without making changes
- `--no-backup` - Skip creating a backup (not recommended)

## Instructions

1. Determine the project to update:
   - Use `--project <name>` if provided
   - Or use current directory if inside a project

2. First check if updates are available:

```bash
python -m orchestrator --project <project-name> --check-updates
```

3. If updates are available, apply them:

```bash
python -m orchestrator --project <project-name> --update
```

Or for a dry run:

```bash
python -m orchestrator --project <project-name> --update --dry-run
```

4. The update process will:
   - Create a backup in `.workflow/backups/<timestamp>/`
   - Sync templates from `project-templates/`
   - Preserve project-overrides/
   - Update `.project-config.json` with new version

5. Display the results showing:
   - Backup ID (if created)
   - Files that were updated
   - New version

## Warning for Breaking Updates

If the update involves a major version change (e.g., 0.x -> 1.x), warn the user:

```
⚠️  Warning: This is a breaking update (0.1.0 -> 1.0.0)
Breaking changes may require manual adjustments.
Continue? [y/N]:
```

## Output Format

```
Update result:
  Status: Updated
  Backup created: 20260121_150000
  Files updated:
    - CLAUDE.md
    - GEMINI.md
    - .cursor/rules
```

## Rollback

If something goes wrong, use the backup to rollback:

```bash
python -m orchestrator --project <project-name> --rollback-backup <backup-id>
```

Or list available backups:

```bash
python -m orchestrator --project <project-name> --list-backups
```

## Usage Examples

```
/update-project --project my-app
/update-project --project my-app --dry-run
/update-project --project my-app --no-backup
```

## Related Commands

- `/check-updates` - Check for available updates
- `/sync-projects` - Sync templates to all projects (without backup)
