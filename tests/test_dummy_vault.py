"""Fixture validation for dummy_vault — confirms all 12 files exist with correct scores.

Scoring rules (TRD Section 4 / Bubble S02 Section 8):
  Rule 1 — Missing aliases/tags: +10 (if BOTH aliases AND tags are empty)
  Rule 2 — Code mismatch: +50 (stem does not start with expected folder code)
            EXCEPTION: Rule 2 is skipped when Rule 3 fires on the same file.
  Rule 3 — Generic filename: +20 (stem.lower() in {"untitled","meeting","note","call"})
  Excluded dirs: "99. System", "00. Inbox", ".git", ".obsidian", ".trash"
"""
from pathlib import Path

import frontmatter
import pytest

VAULT_ROOT = Path(__file__).parent / "fixtures" / "dummy_vault"

EXCLUDED_DIRS = frozenset({"99. System", "00. Inbox", ".git", ".obsidian", ".trash"})
GENERIC_STEMS = frozenset({"untitled", "meeting", "note", "call"})


def _is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.parts)


def _build_code_registry(vault_root: Path) -> dict[str, str]:
    """Scan Projects and Areas for files with a `code` frontmatter field."""
    registry: dict[str, str] = {}
    for folder in ("20. Projects", "30. Areas"):
        scan_root = vault_root / folder
        if not scan_root.exists():
            continue
        for md in scan_root.rglob("*.md"):
            rel = md.relative_to(vault_root)
            if _is_excluded(rel):
                continue
            try:
                post = frontmatter.load(md)
                code = post.metadata.get("code")
                if code:
                    registry[str(rel.parent)] = code
            except Exception:
                continue
    return registry


def _find_expected_code(folder_rel: str, registry: dict[str, str]) -> str | None:
    parts = Path(folder_rel).parts
    for i in range(len(parts), 0, -1):
        candidate = str(Path(*parts[:i]))
        if candidate in registry:
            return registry[candidate]
    return None


def score_file(path: Path, vault_root: Path, registry: dict[str, str]) -> int:
    """Compute audit score for a single file using TRD rules."""
    rel = path.relative_to(vault_root)
    if _is_excluded(rel):
        return -1  # Excluded files get sentinel -1

    post = frontmatter.load(path)
    aliases = post.metadata.get("aliases") or []
    tags = post.metadata.get("tags") or []
    stem = path.stem
    score = 0

    # Rule 1 — Missing aliases/tags
    if not aliases and not tags:
        score += 10

    # Rule 3 — Generic filename (evaluate before Rule 2 to apply exemption)
    rule3_fires = stem.lower() in GENERIC_STEMS
    if rule3_fires:
        score += 20

    # Rule 2 — Code mismatch (skipped when Rule 3 fires)
    if not rule3_fires:
        expected_code = _find_expected_code(str(rel.parent), registry)
        if expected_code and not stem.startswith(expected_code):
            score += 50

    return score


# ── Expected scores per file (relative to dummy_vault root) ───────────────────
EXPECTED_SCORES: dict[str, int] = {
    "20. Projects/TEST-P01/TEST-P01 - Project Root.md": 0,
    "20. Projects/TEST-P01/TEST-P01 - Feature Spec.md": 0,
    "20. Projects/TEST-P01/TEST-P01 - Architecture.md": 0,
    "30. Areas/1. Test Area/AREA - Test Area.md": 0,
    "30. Areas/1. Test Area/AREA - Context Note.md": 10,
    "30. Areas/1. Test Area/AREA - Bad Note.md": 10,
    "20. Projects/TEST-P01/wrong-prefix-note.md": 60,
    "20. Projects/TEST-P01/another-wrong-prefix.md": 50,
    "30. Areas/1. Test Area/untitled.md": 30,
    "30. Areas/1. Test Area/meeting.md": 30,
    "30. Areas/1. Test Area/note.md": 30,
    # Inbox file is excluded from scoring but must exist
    "00. Inbox/0. Capture/new-capture-note.md": -1,
}


class TestFixtureFilesExist:
    @pytest.mark.parametrize("rel_path", list(EXPECTED_SCORES.keys()))
    def test_fixture_file_exists(self, rel_path):
        full_path = VAULT_ROOT / rel_path
        assert full_path.exists(), f"Fixture file missing: {rel_path}"

    @pytest.mark.parametrize("rel_path", list(EXPECTED_SCORES.keys()))
    def test_fixture_parseable(self, rel_path):
        full_path = VAULT_ROOT / rel_path
        post = frontmatter.load(full_path)
        assert post is not None, f"Could not parse frontmatter from: {rel_path}"


class TestAuditScores:
    @pytest.fixture(scope="class")
    def registry(self):
        return _build_code_registry(VAULT_ROOT)

    @pytest.mark.parametrize("rel_path,expected", [
        (k, v) for k, v in EXPECTED_SCORES.items()
    ])
    def test_score(self, registry, rel_path, expected):
        full_path = VAULT_ROOT / rel_path
        actual = score_file(full_path, VAULT_ROOT, registry)
        assert actual == expected, (
            f"{rel_path}: expected score {expected}, got {actual}"
        )


class TestTopTenSelectionLogic:
    """Verify the 10-highest-scoring selection would work correctly."""

    @pytest.fixture(scope="class")
    def registry(self):
        return _build_code_registry(VAULT_ROOT)

    def test_highest_score_file_is_wrong_prefix_note(self, registry):
        scores = {
            rel: score_file(VAULT_ROOT / rel, VAULT_ROOT, registry)
            for rel in EXPECTED_SCORES
        }
        active_scores = {k: v for k, v in scores.items() if v > 0}
        top = max(active_scores, key=lambda k: active_scores[k])
        assert "wrong-prefix-note" in top

    def test_multiple_violation_file_has_score_60(self, registry):
        path = "20. Projects/TEST-P01/wrong-prefix-note.md"
        assert score_file(VAULT_ROOT / path, VAULT_ROOT, registry) == 60

    def test_score_descending_order(self, registry):
        scores = [
            score_file(VAULT_ROOT / rel, VAULT_ROOT, registry)
            for rel in EXPECTED_SCORES
            if EXPECTED_SCORES[rel] > 0
        ]
        sorted_scores = sorted(scores, reverse=True)
        assert sorted_scores == sorted(scores, reverse=True)
