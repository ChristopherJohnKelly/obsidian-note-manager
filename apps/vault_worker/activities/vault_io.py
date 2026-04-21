"""Vault I/O Activities for Temporal worker.

All Activities are synchronous def functions — Temporal executes them in a
ThreadPoolExecutor automatically. Do not convert to async def.
pathlib and python-frontmatter are blocking I/O libraries.
"""

from __future__ import annotations

from pathlib import Path

import frontmatter
from temporalio import activity

from packages.shared.models import CodeRegistryEntry, Frontmatter, ValidationResult, VaultNote

# ---------------------------------------------------------------------------
# Constants (ported verbatim from src_v2)
# ---------------------------------------------------------------------------

EXCLUDED_DIRS = frozenset({
    "99. System",
    "00. Inbox",
    ".git",
    ".obsidian",
    ".trash",
})

BAD_TITLES = frozenset({"untitled", "meeting", "note", "call"})

PROJECTS_FOLDER = "20. Projects"
AREAS_FOLDER = "30. Areas"
RESOURCES_FOLDER = "40. Resources"


# ---------------------------------------------------------------------------
# Internal helpers (not Activities)
# ---------------------------------------------------------------------------


def _normalize_to_list(value: str | list | None) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if v]
    if isinstance(value, str):
        if "," in value:
            return [a.strip() for a in value.split(",") if a.strip()]
        return [value.strip()] if value.strip() else []
    return []


def _metadata_to_frontmatter(metadata: dict) -> Frontmatter:
    aliases = _normalize_to_list(metadata.get("aliases"))
    tags = _normalize_to_list(metadata.get("tags"))
    return Frontmatter(
        type=metadata.get("type"),
        status=metadata.get("status"),
        title=metadata.get("title"),
        aliases=aliases,
        tags=tags,
        code=metadata.get("code"),
        folder=metadata.get("folder"),
        **{k: v for k, v in metadata.items() if k not in ("type", "status", "title", "aliases", "tags", "code", "folder")},
    )


def _is_excluded(path: Path, vault_root: Path) -> bool:
    try:
        rel_path = path.relative_to(vault_root)
        return any(excluded in rel_path.parts for excluded in EXCLUDED_DIRS)
    except ValueError:
        return True


def _build_registry(vault_root: Path) -> dict[str, str]:
    """Build folder -> code mapping from Areas and Projects."""
    registry: dict[str, str] = {}
    for folder_name in (AREAS_FOLDER, PROJECTS_FOLDER):
        scan_path = vault_root / folder_name
        if not scan_path.exists():
            continue
        for file_path in scan_path.rglob("*.md"):
            if _is_excluded(file_path, vault_root):
                continue
            try:
                post = frontmatter.load(file_path)
                code = post.metadata.get("code")
                if not code:
                    continue
                folder = str(file_path.relative_to(vault_root).parent)
                registry[folder] = code
            except Exception:
                continue
    return registry


def _find_expected_code(registry: dict[str, str], folder_path: str) -> str | None:
    """Find expected project code for a folder by walking up the tree."""
    path_parts = Path(folder_path).parts
    for i in range(len(path_parts), 0, -1):
        check_path = str(Path(*path_parts[:i]))
        if check_path in registry:
            return registry[check_path]
    return None


def _validate_vault_note(note: VaultNote, registry: dict[str, str]) -> ValidationResult | None:
    """Evaluate validation rules. Returns ValidationResult if issues found, else None."""
    score = 0
    reasons: list[str] = []

    # Rule 1: Missing aliases AND tags → +10
    if not note.frontmatter.aliases and not note.frontmatter.tags:
        score += 10
        reasons.append("Missing aliases/tags")

    # Rule 3: Generic filename → +20 (check before Rule 2)
    rule3_fired = note.path.stem.lower() in BAD_TITLES
    if rule3_fired:
        score += 20
        reasons.append("Generic Filename")

    # Rule 2: Code mismatch → +50 (skip if Rule 3 also fires)
    if not rule3_fired:
        folder_path = str(note.path.parent)
        expected_code = _find_expected_code(registry, folder_path)
        if expected_code and not note.path.stem.startswith(expected_code):
            score += 50
            reasons.append(f"Missing Project Code: {expected_code}")

    if score == 0:
        return None
    return ValidationResult(path=note.path, score=score, reasons=reasons)


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------


@activity.defn
def read_note(vault_root: str, path: str) -> VaultNote | None:
    """Read a note from vault_root/path. Returns None if not found.

    Synchronous def: Temporal runs this in a ThreadPoolExecutor automatically.
    """
    root = Path(vault_root)
    full_path = root / path
    if not full_path.exists():
        return None
    try:
        post = frontmatter.load(full_path)
    except Exception:
        return None
    fm = _metadata_to_frontmatter(dict(post.metadata))
    rel_path = full_path.relative_to(root)
    return VaultNote(path=rel_path, frontmatter=fm, body=post.content or "")


@activity.defn
def save_note(vault_root: str, path: str, note: VaultNote) -> None:
    """Persist a note to vault_root/path."""
    full_path = Path(vault_root) / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = note.frontmatter.model_dump(exclude_none=False)
    post = frontmatter.Post(note.body, **metadata)
    content = frontmatter.dumps(post)
    full_path.write_text(content, encoding="utf-8")


@activity.defn
def delete_note(vault_root: str, path: str) -> None:
    """Delete the file at vault_root/path."""
    full_path = Path(vault_root) / path
    if full_path.exists():
        full_path.unlink()


@activity.defn
def list_notes_in(vault_root: str, directory: str) -> list[str]:
    """List .md files in vault_root/directory. Returns relative paths as strings."""
    root = Path(vault_root)
    full_dir = root / directory
    if not full_dir.exists() or not full_dir.is_dir():
        return []
    return sorted(
        str(p.relative_to(root))
        for p in full_dir.glob("*.md")
    )


@activity.defn
def read_raw(vault_root: str, path: str) -> str | None:
    """Return raw file content or None if not found. No frontmatter parsing."""
    full_path = Path(vault_root) / path
    if not full_path.exists():
        return None
    try:
        return full_path.read_text(encoding="utf-8")
    except Exception:
        return None


@activity.defn
def scan_vault(vault_root: str) -> list[ValidationResult]:
    """Scan vault and return ValidationResult for files with quality issues.

    Scans 20. Projects/ and 30. Areas/. Excludes EXCLUDED_DIRS.
    Returns only files with score > 0.
    """
    root = Path(vault_root)
    registry = _build_registry(root)
    results: list[ValidationResult] = []
    for folder_name in (PROJECTS_FOLDER, AREAS_FOLDER):
        scan_path = root / folder_name
        if not scan_path.exists():
            continue
        for file_path in scan_path.rglob("*.md"):
            if _is_excluded(file_path, root):
                continue
            note = read_note(vault_root, str(file_path.relative_to(root)))
            if note is None:
                continue
            validation = _validate_vault_note(note, registry)
            if validation is not None:
                results.append(validation)
    return results


@activity.defn
def validate_note(vault_root: str, path: str) -> ValidationResult | None:
    """Validate a single note. Returns ValidationResult if issues found, else None."""
    registry = _build_registry(Path(vault_root))
    note = read_note(vault_root, path)
    if note is None:
        return None
    return _validate_vault_note(note, registry)


@activity.defn
def get_skeleton(vault_root: str) -> str:
    """Return vault skeleton (valid link targets) for deep linking."""
    root = Path(vault_root)
    skeleton: list[str] = []
    for folder_name in (AREAS_FOLDER, PROJECTS_FOLDER, RESOURCES_FOLDER):
        scan_path = root / folder_name
        if not scan_path.exists():
            continue
        for file_path in scan_path.rglob("*.md"):
            if _is_excluded(file_path, root):
                continue
            try:
                post = frontmatter.load(file_path)
                title = post.metadata.get("title", file_path.stem)
                aliases = _normalize_to_list(post.metadata.get("aliases"))
                rel_path = file_path.relative_to(root)
                entry = f"- [[{title}]] ({rel_path})"
                if aliases:
                    entry += f" [Aliases: {', '.join(aliases)}]"
                skeleton.append(entry)
            except Exception:
                continue
    return "\n".join(skeleton)


@activity.defn
def get_code_registry(vault_root: str) -> list[CodeRegistryEntry]:
    """Return code registry entries from Areas and Projects."""
    root = Path(vault_root)
    entries: list[CodeRegistryEntry] = []
    for folder_name in (AREAS_FOLDER, PROJECTS_FOLDER):
        scan_path = root / folder_name
        if not scan_path.exists():
            continue
        for file_path in scan_path.rglob("*.md"):
            if _is_excluded(file_path, root):
                continue
            try:
                post = frontmatter.load(file_path)
                code = post.metadata.get("code")
                if not code:
                    continue
                folder = str(file_path.relative_to(root).parent)
                entries.append(
                    CodeRegistryEntry(
                        code=code,
                        name=file_path.stem,
                        type=post.metadata.get("type", ""),
                        folder=folder,
                    )
                )
            except Exception:
                continue
    return entries


@activity.defn
def check_vault_dir_state(vault_path: str) -> str:
    """Inspect vault_path and return its state.

    Returns: 'empty' | 'valid_repo' | 'invalid'

    Synchronous def: uses pathlib (blocking I/O). Temporal runs in ThreadPoolExecutor.
    This Activity exists solely so the workflow never touches the filesystem directly.
    """
    vault = Path(vault_path)
    if not vault.exists() or not any(vault.iterdir()):
        return "empty"
    if (vault / ".git").exists():
        return "valid_repo"
    return "invalid"
