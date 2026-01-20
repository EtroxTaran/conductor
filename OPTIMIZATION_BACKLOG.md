# Optimization Backlog

## Completed

- [x] P0: Git subprocess overhead (batched operations via GitOperationsManager)
- [x] P0: Timeout stacking (unified wait() pattern in phase2/phase4)
- [x] P0: Subprocess streaming (memory-efficient output capture in phase3)

## P1 - High Value (Next Sprint)

- [ ] Duplicate `_process_result()` methods in phase2/phase4 → extract to BasePhase
- [ ] Hardcoded config values → create config/orchestrator.yaml
- [ ] Wire observability into agent execution

## P2 - Medium Value

- [ ] Context drift detection not capturing on first call
- [ ] No error recovery for partial agent failures
- [ ] Missing log rotation (disk space risk)

## P3 - Nice to Have

- [ ] Documentation gaps in internal APIs
- [ ] Test coverage for timeout/chaos scenarios
- [ ] Cost tracking integration
