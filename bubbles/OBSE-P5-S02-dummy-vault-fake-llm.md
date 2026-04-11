---
type: bubble
status: pending
step_id: S02
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior Python Test Engineer building a deterministic test harness.
**Objective:** Create the Dummy Vault fixture files and the Fake LLM service. These are the two external dependencies that must be mocked before any Activity or Workflow can be safely tested.
**Constraints:**
- Python 3.12
- The Dummy Vault is static Markdown files — no code generates them, they are committed fixtures
- The Fake LLM must be a class that implements the same interface as the real Gemini adapter, returning hardcoded but realistic responses
- All Fake LLM responses must be deterministic (same input → same output, no randomness)

---

## 1. Context

**Feature:** TRD Section 6, Phase 0 (Test Harness)
**Depends On:** S01 (Monorepo Scaffolding — `packages/shared/models.py` must exist)
**Current State:** Monorepo scaffolded, shared models defined and tested.
**Target State:** A fully populated `tests/fixtures/dummy_vault/` and a working `tests/mocks/fake_llm.py` that Activity tests can import and use.

---

## 2. Input

- `packages/shared/models.py` — `VaultNote`, `Frontmatter`, `ValidationResult` (read)
- `obsidian-note-manager/src_v2/infrastructure/file_system/adapters.py` — audit scoring rules to mirror in fixtures (read-only reference)
- TRD Section 6 Phase 0 — dummy vault composition spec

---

## 3. Required Output

**Dummy Vault (12 files, committed as fixtures):**
- [ ] `tests/fixtures/dummy_vault/20. Projects/TEST-P01/TEST-P01 - Project Root.md` — clean file (all rules pass)
- [ ] `tests/fixtures/dummy_vault/20. Projects/TEST-P01/TEST-P01 - Feature Spec.md` — clean file
- [ ] `tests/fixtures/dummy_vault/20. Projects/TEST-P01/TEST-P01 - Architecture.md` — clean file
- [ ] `tests/fixtures/dummy_vault/30. Areas/1. Test Area/AREA - Test Area.md` — clean root note with `code: AREA`
- [ ] `tests/fixtures/dummy_vault/30. Areas/1. Test Area/AREA - Context Note.md` — missing aliases/tags (Rule 1 violation, +10)
- [ ] `tests/fixtures/dummy_vault/30. Areas/1. Test Area/AREA - Bad Note.md` — missing aliases/tags only (Rule 1, +10); filename starts with "AREA" so Rule 2 does not fire
- [ ] `tests/fixtures/dummy_vault/20. Projects/TEST-P01/wrong-prefix-note.md` — code mismatch AND missing aliases/tags (Rule 1 +10, Rule 2 +50 = score 60); this is the "multiple violations ≥ 60" file required by TRD Phase 0
- [ ] `tests/fixtures/dummy_vault/20. Projects/TEST-P01/another-wrong-prefix.md` — code mismatch only (Rule 2, +50); has valid aliases/tags
- [ ] `tests/fixtures/dummy_vault/30. Areas/1. Test Area/untitled.md` — generic filename + missing aliases/tags (Rule 1 +10, Rule 3 +20 = 30); Rule 2 is exempt when Rule 3 fires — see scoring rules in Section 8
- [ ] `tests/fixtures/dummy_vault/30. Areas/1. Test Area/meeting.md` — generic filename + missing aliases/tags (Rule 1 +10, Rule 3 +20 = 30); Rule 2 exempt
- [ ] `tests/fixtures/dummy_vault/30. Areas/1. Test Area/note.md` — generic filename + missing aliases/tags (Rule 1 +10, Rule 3 +20 = 30); Rule 2 exempt
- [ ] `tests/fixtures/dummy_vault/00. Inbox/0. Capture/new-capture-note.md` — raw inbox note for Filer tests

**Fake LLM:**
- [ ] `tests/mocks/fake_llm.py` — `FakeLLMProvider` class with deterministic responses
- [ ] `tests/test_fake_llm.py` — tests proving determinism and correct response format

---

## 4. Acceptance Criteria

- [ ] The 12 fixture files exist and are valid Markdown with YAML frontmatter parseable by `python-frontmatter`
- [ ] Scanning the dummy vault with the audit scoring logic produces exactly the expected scores: 3 clean files (score 0), and specific non-zero scores for the remaining files
- [ ] `FakeLLMProvider.generate_proposal()` returns a string containing valid `%%FILE%%` markers
- [ ] `FakeLLMProvider.generate_fix()` returns a string containing valid frontmatter YAML fixes
- [ ] Calling `FakeLLMProvider` with identical inputs twice returns identical outputs (determinism test)
- [ ] `FakeLLMProvider` raises `NotImplementedError` on any method not yet implemented (no silent failures)

---

## 5. Scope Boundary

**May modify:** `tests/fixtures/`, `tests/mocks/`, `tests/test_fake_llm.py`
**Must not modify:** `packages/`, `apps/`, any production code

---

## 6. TDD Constraints

- Write `tests/test_fake_llm.py` before implementing `fake_llm.py`
- Write a validation test that scans the dummy vault and asserts expected scores — run it to see it fail (fixture files not yet created), then create the fixtures to pass it
- Commit fixture files and fake LLM separately (two commits)

---

## 7. Step-by-Step Plan

1. Write `tests/test_fake_llm.py` asserting the `FakeLLMProvider` interface, determinism, and response format. Run — fails (class not defined).
2. Implement `tests/mocks/fake_llm.py` with hardcoded responses. Run — tests pass.
3. Write a fixture validation test in `tests/test_dummy_vault.py` that reads all fixture files, confirms frontmatter is parseable, and checks expected audit scores using the scoring rules from `src_v2`.
4. Create the 12 fixture files with appropriate frontmatter to produce the expected scores.
5. Run fixture validation — all scores match. Commit both fixtures and validation test.
6. Verify the top-10 selection logic would return the correct files in score-descending order.

---

## 8. Reference Material

### Audit scoring rules (from src_v2 — must be mirrored by fixtures)

```
Rule 1 — Missing aliases/tags: +10 (if both aliases AND tags are empty)
Rule 2 — Code mismatch: +50 (filename stem does not start with expected project/area code)
           EXCEPTION: Rule 2 is NOT evaluated if Rule 3 fires on the same file.
           Rationale: a generically named file (untitled, meeting, etc.) predictably
           lacks a code prefix — this is a symptom of the same underlying condition,
           not an independent violation. Flagging both would double-penalise the same issue.
Rule 3 — Generic filename: +20 (stem.lower() in {"untitled", "meeting", "note", "call"})
Excluded dirs: "99. System", "00. Inbox", ".git", ".obsidian", ".trash"
```

### Expected dummy vault scores

| File | Rule 1 | Rule 2 | Rule 3 | Total |
| :--- | :--- | :--- | :--- | :--- |
| TEST-P01 - Project Root.md | — | — | — | 0 (clean) |
| TEST-P01 - Feature Spec.md | — | — | — | 0 (clean) |
| TEST-P01 - Architecture.md | — | — | — | 0 (clean) |
| AREA - Test Area.md | — | — | — | 0 (clean) |
| AREA - Context Note.md | +10 | — | — | 10 |
| AREA - Bad Note.md | +10 | — | — | 10 |
| wrong-prefix-note.md | +10 | +50 | — | **60** (multiple violations ≥ 60) |
| another-wrong-prefix.md | — | +50 | — | 50 |
| untitled.md | +10 | *(exempt — R3 fires)* | +20 | 30 |
| meeting.md | +10 | *(exempt — R3 fires)* | +20 | 30 |
| note.md | +10 | *(exempt — R3 fires)* | +20 | 30 |
| new-capture-note.md | *(excluded — in 00. Inbox)* | — | — | excluded |

### Example clean fixture frontmatter

```yaml
---
type: project
status: active
title: "TEST-P01 - Project Root"
aliases: ["Test Project"]
tags: ["type/project"]
code: TEST-P01
folder: "20. Projects/TEST-P01"
---

# TEST-P01 - Project Root

Test project root note for fixture validation.
```

### FakeLLMProvider interface

```python
# tests/mocks/fake_llm.py
class FakeLLMProvider:
    """Deterministic LLM that returns hardcoded responses. No API calls."""

    FAKE_PROPOSAL = """%%FILE%%
path: 30. Areas/1. Test Area/AREA - Filed Note.md
---
type: content
status: active
title: "Filed Note"
aliases: ["Test Filed"]
tags: ["type/content"]
---
# Filed Note
Fake content for testing.
%%END%%"""

    FAKE_FIX = """%%FILE%%
path: {original_path}
---
type: content
status: active
title: "Fixed Note"
aliases: ["Fixed"]
tags: ["type/content"]
---
# Fixed Note
Fixed content.
%%END%%"""

    def generate_proposal(self, instructions: str, body: str,
                          context: str, skeleton: str) -> str:
        return self.FAKE_PROPOSAL

    def generate_fix(self, instructions: str, body: str,
                     context: str, skeleton: str) -> str:
        return self.FAKE_FIX
```
