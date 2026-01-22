# Sync Rules Skill

Synchronize shared rules from `shared-rules/` to all agent context files.

## Overview

This skill propagates rules from the central `shared-rules/` directory to:
- `CLAUDE.md` (this file)
- Project-level context files
- Agent-specific overrides

## Usage

```
/sync-rules
```

## How It Works

1. **Read shared rules**:
   ```
   shared-rules/
   ├── core-rules.md
   ├── coding-standards.md
   ├── guardrails.md
   ├── cli-reference.md
   ├── lessons-learned.md
   └── agent-overrides/
       └── claude.md
   ```

2. **Assemble CLAUDE.md**:
   - Start with claude-specific header
   - Append shared rules in order
   - Add lessons learned at end

3. **Update timestamp**:
   ```markdown
   <!-- AUTO-GENERATED from shared-rules/ -->
   <!-- Last synced: 2026-01-22 12:00:00 -->
   ```

## Execution

```bash
python scripts/sync-rules.py
```

Or manually:
1. Read all files from `shared-rules/`
2. Concatenate in order
3. Write to `CLAUDE.md`

## File Order

1. `agent-overrides/claude.md` - Claude-specific rules (header)
2. `core-rules.md` - Core workflow rules
3. `coding-standards.md` - Coding guidelines
4. `guardrails.md` - Safety guardrails
5. `cli-reference.md` - CLI tool reference
6. `lessons-learned.md` - Lessons from past issues

## Validation

After sync, verify:
- [ ] CLAUDE.md updated
- [ ] Timestamp current
- [ ] No merge conflicts
- [ ] Rules are complete

## When to Sync

Run sync after:
- Adding a new lesson learned
- Updating shared rules
- Before starting a new workflow
- After pulling changes from git
