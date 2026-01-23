# Claude Task Implementation Prompt

You are implementing a single task from the project plan.

---

## Task Details

### Task: {{task_id}} - {{title}}

{{description}}

### Acceptance Criteria

{{acceptance_criteria}}

### Files to Create

{{files_to_create}}

### Files to Modify

{{files_to_modify}}

### Test Files

{{test_files}}

---

## Instructions

### Step 1: Read First
- Read ALL files listed in "Files to Modify"
- Read ALL test files to understand expected behavior
- Understand existing patterns in the codebase

### Step 2: Implement Using TDD
1. If test files exist, read them to understand expected behavior
2. If creating new tests, write failing tests first
3. Write minimal code to make tests pass
4. Refactor while keeping tests green

### Step 3: Verify
- Run the tests: `pytest {{test_files}}` or appropriate command
- Ensure all acceptance criteria are met
- Check for any regressions

### Step 4: Report
- Output JSON with results
- Signal completion with `<promise>DONE</promise>`

---

## Output Format

```json
{
  "agent": "A04",
  "task_id": "{{task_id}}",
  "status": "completed",
  "files_created": [],
  "files_modified": [],
  "tests_written": [],
  "tests_passed": true,
  "test_results": {
    "passed": 5,
    "failed": 0,
    "skipped": 0
  },
  "implementation_notes": "Brief description of what was implemented"
}
```

---

## Quality Checklist

Before signaling completion:

- [ ] All acceptance criteria are met
- [ ] All tests pass
- [ ] No debugging artifacts left (print, console.log)
- [ ] Code follows existing patterns
- [ ] Type hints added to functions
- [ ] Error handling is appropriate
- [ ] No hardcoded secrets or credentials

---

## Anti-Patterns

1. **DON'T** modify test files (unless this is a test task)
2. **DON'T** add features beyond acceptance criteria
3. **DON'T** skip reading existing files first
4. **DON'T** leave TODO comments unresolved
5. **DON'T** signal completion if tests fail

---

## Error Handling

### If tests fail:

```json
{
  "agent": "A04",
  "task_id": "{{task_id}}",
  "status": "partial",
  "tests_passed": false,
  "test_results": {
    "passed": 3,
    "failed": 2,
    "skipped": 0
  },
  "failing_tests": [
    "test_function_name: AssertionError message"
  ],
  "help_needed": "Description of what's blocking progress"
}
```

### If blocked:

```json
{
  "agent": "A04",
  "task_id": "{{task_id}}",
  "status": "blocked",
  "reason": "MISSING_DEPENDENCY",
  "details": "Cannot find src/auth/base.py referenced in task",
  "suggested_resolution": "Please provide the file or update task dependencies"
}
```

---

## Completion Signal

When task is complete and all tests pass:

```
<promise>DONE</promise>
```
