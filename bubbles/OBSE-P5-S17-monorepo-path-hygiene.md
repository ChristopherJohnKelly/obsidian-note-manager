---
type: bubble
status: pending
step_id: S17
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble, type/hygiene ]
---

## LLM Instructions

**Role:** You are a Senior Python Engineer executing a mechanical directory-rename refactor.
**Objective:** Normalise every `apps/` sub-package from hyphenated names to underscored names so Python can import them. Remove one dead scaffold. Update two sub-package `pyproject.toml` files and the root coverage-omit line. No behaviour changes, no new tests.
**Constraints:**
- This is a hygiene refactor, not a feature. **TDD does not apply — see §6.**
- All changes must be applied together in a single commit so the tree is never left in a half-renamed state.
- Use `git mv` (not `mv` + `git add`) so rename history is preserved.
- After the refactor, `grep -r "apps/\(vault-worker\|copilot-ui\|github-runner\)"` over the whole repo must return zero code/config matches (docs and CHANGELOG-like files are allowed if explicitly noted).

---

## 1. Context

**Feature:** Fallout from S01 (Monorepo Scaffolding), surfaced during S04 implementation and confirmed during S07 review.
**Depends On:** — (no upstream step)
**Current State:** The monorepo has three `apps/` sub-packages scaffolded with hyphenated names (`apps/vault-worker/`, `apps/copilot-ui/`, `apps/github-runner/`). Python cannot import hyphenated directories, so S04 silently migrated real code to `apps/vault_worker/` (underscore) and left the hyphenated sibling in place as dead scaffold. S13 (github-runner refactor) and S14 (copilot-ui refactor) are blocked by this: they would either reintroduce hyphens or fail on first import.
**Target State:** One canonical underscored directory per app. No hyphenated `apps/*-*` directories remain. All `pyproject.toml` and coverage config files point at the underscored paths. All bubble specs (already done, queued, or in-progress) reference underscored paths.

---

## 2. Input

- `apps/vault-worker/` — dead scaffold (contains only `pyproject.toml` + two docstring-only `__init__.py`); real code lives in `apps/vault_worker/`
- `apps/copilot-ui/` — placeholder scaffold (contains only `pyproject.toml` + docstring-only `__init__.py`); will be populated by S14
- `apps/github-runner/` — placeholder scaffold (contains only `pyproject.toml` + docstring-only `__init__.py`); will be populated by S13
- `pyproject.toml` (root) — line 43 `[tool.coverage.run] omit = [...]` references two stale hyphenated paths

---

## 3. Required Output

The diff produced by this bubble MUST consist of exactly the following changes and nothing else:

**Deletions:**
- [ ] `apps/vault-worker/` — entire directory removed (`git rm -r`)

**Renames (preserving history via `git mv`):**
- [ ] `apps/copilot-ui/` → `apps/copilot_ui/`
- [ ] `apps/github-runner/` → `apps/github_runner/`

**Edits inside renamed dirs:**
- [ ] `apps/copilot_ui/pyproject.toml` — change `packages = ["apps/copilot-ui"]` → `packages = ["apps/copilot_ui"]`
- [ ] `apps/github_runner/pyproject.toml` — change `packages = ["apps/github-runner"]` → `packages = ["apps/github_runner"]`

**Edits in root config:**
- [ ] `pyproject.toml` line 43 — in the `[tool.coverage.run]` `omit` list, replace `"apps/copilot-ui/app.py"` with `"apps/copilot_ui/app.py"` and replace `"apps/vault-worker/activities/git_ops.py"` with `"apps/vault_worker/activities/git_ops.py"`

---

## 4. Acceptance Criteria

- [ ] `ls apps/` returns exactly: `__init__.py  copilot_ui  github_runner  vault_worker` (no hyphenated entries)
- [ ] `apps/copilot_ui/pyproject.toml` contains `packages = ["apps/copilot_ui"]` and no hyphenated references
- [ ] `apps/github_runner/pyproject.toml` contains `packages = ["apps/github_runner"]` and no hyphenated references
- [ ] `pyproject.toml` (root) line in `[tool.coverage.run]` `omit` list uses only underscored paths
- [ ] `grep -r "apps/vault-worker\|apps/copilot-ui\|apps/github-runner" --include='*.py' --include='*.toml'` returns zero matches
- [ ] `uv run pytest` (or the project's invocation) passes with no regressions — existing test count unchanged, no new failures
- [ ] `git log --follow apps/copilot_ui/pyproject.toml` shows the pre-rename history (confirms `git mv` was used, not `rm` + `add`)
- [ ] The single commit contains only the files listed in §3 — no incidental edits

---

## 5. Scope Boundary

**May modify:** `apps/copilot-ui/` (renamed), `apps/github-runner/` (renamed), `apps/vault-worker/` (deleted), `apps/copilot_ui/pyproject.toml`, `apps/github_runner/pyproject.toml`, root `pyproject.toml` (coverage omit line only).

**Must not modify:** Any file under `apps/vault_worker/`, any file under `packages/`, any file under `tests/`, any bubble file under `bubbles/`, any file under `.github/`, any file under `docker/` or `infra/`. No edits to `LEARNINGS.md`, `LOOP.md`, `PLAN.md`, `architecture.md`, or `TRD.md`.

**Note:** Bubble-spec documentation updates (propagating underscores into the remaining 13 bubble files that still reference hyphens) are being handled out-of-band in the same commit as this bubble's creation; they are NOT part of the implementation diff for this bubble.

---

## 6. TDD Exception — Hygiene Refactor

**TDD does not apply to this bubble.** Rationale:

- No new behaviour is being added. Every public/importable symbol retains the same API.
- There is no meaningful "red" test. A test like `assert Path("apps/copilot_ui").exists()` is a tautology that passes by virtue of the directory structure itself.
- The implicit regression test is the full existing test suite passing unchanged, plus the grep-based acceptance criteria in §4.

**Instead of Red → Green → Refactor, follow Execute → Verify:**

1. Execute the diff exactly as specified in §3.
2. Verify acceptance criteria §4 one-by-one.

Do **not** write new tests. Do **not** add assertions. Do **not** modify existing tests. If an existing test breaks, that is a regression; fix the cause (the rename) rather than the test.

**For cc-obsidian reviewers:** the expected diff is small and mechanical. Verify by comparing the actual diff against §3 line-by-line. Absence of new test coverage is expected and correct for this bubble type.

---

## 7. Step-by-Step Plan

1. `git rm -r apps/vault-worker/`
2. `git mv apps/copilot-ui apps/copilot_ui`
3. Edit `apps/copilot_ui/pyproject.toml`: replace `"apps/copilot-ui"` with `"apps/copilot_ui"` in the `packages` list.
4. `git mv apps/github-runner apps/github_runner`
5. Edit `apps/github_runner/pyproject.toml`: replace `"apps/github-runner"` with `"apps/github_runner"` in the `packages` list.
6. Edit root `pyproject.toml`: on the `omit` line in `[tool.coverage.run]`, replace the two hyphenated paths with their underscored equivalents.
7. Run `git status` to verify exactly the files listed in §3 are modified and nothing else.
8. Run `grep -r "apps/\(vault-worker\|copilot-ui\|github-runner\)" --include='*.py' --include='*.toml'` to verify zero matches.
9. Run the test suite — it must pass with no regressions and no new failures.
10. Commit as a single atomic commit with a descriptive message.

---

## 8. Reference Material

### Why the hyphenated names don't work

Python module imports use the `import package.module` syntax, which is translated into directory/file lookups. Directory names containing hyphens cannot be used as import path components — `import apps.copilot-ui` is a syntax error (hyphen is minus operator) and `importlib.import_module("apps.copilot-ui")` fails because the identifier isn't a valid Python name. This is why S04 silently created `apps/vault_worker/` alongside the scaffolded `apps/vault-worker/` — it had no choice.

Project names on PyPI can contain hyphens (PEP 503 normalises them for indexing), which is why the scaffolding generator produced hyphenated directory names to match the `name = "obsidian-vault-worker"` project identifier. But PyPI project names and Python package names are decoupled: the `[project] name` field is cosmetic, while `[tool.hatch.build.targets.wheel] packages` points at on-disk directories that MUST be valid Python identifiers.

### Expected final directory state

```
apps/
├── __init__.py
├── copilot_ui/
│   ├── __init__.py
│   └── pyproject.toml
├── github_runner/
│   ├── __init__.py
│   └── pyproject.toml
└── vault_worker/
    ├── __init__.py
    ├── activities/
    ├── core/
    └── workflows/
```

### Git command reference

```bash
# Delete dead scaffold
git rm -r apps/vault-worker/

# Rename placeholder scaffolds (preserves history)
git mv apps/copilot-ui apps/copilot_ui
git mv apps/github-runner apps/github_runner
```

### Root pyproject.toml line to change

Before:
```toml
omit = ["*/tests/*", "*/__pycache__/*", "apps/copilot-ui/app.py", "apps/vault-worker/activities/git_ops.py"]
```

After:
```toml
omit = ["*/tests/*", "*/__pycache__/*", "apps/copilot_ui/app.py", "apps/vault_worker/activities/git_ops.py"]
```
