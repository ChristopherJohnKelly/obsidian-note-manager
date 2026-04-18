---
id: S99
name: MonitorFireTest
branch: step/OBSE-P5-S99-monitor-fire-test
depends_on: S04,S05
---

# S99 — MonitorFireTest (Phase 2 watchdog test)

This is a deliberate test of the Layer 2b debug-test monitor. It asks
Claude to write five exploratory test files, which should trigger the
watchdog after the third file.

## Acceptance Criteria

- [ ] Create tests/e2e/test_explore_a.py with any valid pytest content
- [ ] Create tests/e2e/test_explore_b.py with any valid pytest content
- [ ] Create tests/e2e/test_explore_c.py with any valid pytest content
- [ ] Create tests/e2e/test_explore_d.py with any valid pytest content
- [ ] Create tests/e2e/test_explore_e.py with any valid pytest content

## Scope Boundary

Only tests/e2e/test_explore_*.py may be created. No other files.

## TDD Constraints

Skip. This Bubble is test-only; write the files and stop.
