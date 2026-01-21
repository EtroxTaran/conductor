# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-01-21

### Added

- **Project Update Mechanism**: New `/check-updates` and `/update-project` slash commands
  - Check for available updates with version comparison
  - Apply updates safely with automatic backup
  - Support for `--dry-run` flag to preview changes
  - Rollback capability from backups
- **Version Tracking**: Projects now track `meta_architect_version` for update detection
- **Update Policies**: Configurable update behavior (`auto`, `prompt`, `manual`)
- **Rich Progress Display**: Enhanced status dashboard with Real-time progress visualization
- **Observability System**: Action logging and error aggregation for debugging
- **Ralph Wiggum Loop**: Iterative TDD implementation with fresh context per iteration
- **Task-Based Execution**: Break PRODUCT.md into discrete tasks with verification after each
- **Linear Integration**: Optional sync of tasks to Linear for project management

### Changed

- Template sync now tracks version information
- Projects store `last_sync_version` for changelog display
- Improved error messages for version mismatches

### Fixed

- CLI flag corrections for Cursor and Gemini agents
- Context degradation on long implementations via Ralph loop

## [0.1.0] - 2026-01-15

### Added

- Initial release of multi-agent orchestration system
- 5-phase workflow: Planning, Validation, Implementation, Verification, Completion
- LangGraph-based workflow with native parallelism
- Support for Claude Code, Cursor CLI, and Gemini CLI agents
- Project templates: `react-tanstack`, `node-api`, `nx-fullstack`, `java-spring`, `base`
- Nested architecture with projects in `projects/` directory
- State persistence and workflow resumability
- Auto-commit after successful phases
- Conflict resolution between reviewers

### Developer Notes

- First public release
- Requires Python 3.10+
- CLI tools: `claude`, `cursor-agent`, `gemini` must be installed

---

## Version History Summary

| Version | Date | Highlights |
|---------|------|------------|
| 0.2.0 | 2026-01-21 | Update mechanism, observability, Ralph loop |
| 0.1.0 | 2026-01-15 | Initial release |
