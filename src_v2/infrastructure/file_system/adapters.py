"""File system adapters for vault storage."""

import os
from pathlib import Path

import frontmatter

from src_v2.core.domain.models import Frontmatter, Note, ValidationResult
from src_v2.core.interfaces.ports import VaultRepository

EXCLUDED_DIRS = frozenset({
    "99. System",
    "00. Inbox",
    ".git",
    ".obsidian",
    ".trash",
})

BAD_TITLES = frozenset({"untitled", "meeting", "note", "call"})


def _normalize_to_list(value: str | list | None) -> list[str]:
    """Normalize aliases/tags to list[str]."""
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
    """Convert raw metadata dict to Frontmatter model."""
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
    """Check if path is in an excluded directory."""
    try:
        rel_path = path.relative_to(vault_root)
        return any(excluded in rel_path.parts for excluded in EXCLUDED_DIRS)
    except ValueError:
        return True


class ObsidianFileSystemAdapter(VaultRepository):
    """Adapter for reading/writing Obsidian notes on disk."""

    def __init__(
        self,
        vault_root: Path | str,
        *,
        projects_folder: str | None = None,
        areas_folder: str | None = None,
    ) -> None:
        self.vault_root = Path(vault_root)
        self.projects_folder = projects_folder or os.getenv("OBSIDIAN_PROJECTS_FOLDER", "20. Projects")
        self.areas_folder = areas_folder or os.getenv("OBSIDIAN_AREAS_FOLDER", "30. Areas")
        self._registry: dict[str, str] = {}

    def _resolve_path(self, path: Path) -> Path:
        """Resolve path relative to vault_root if not absolute."""
        p = Path(path)
        if not p.is_absolute():
            return self.vault_root / p
        return p

    def _build_registry(self) -> dict[str, str]:
        """Build folder -> code mapping from Areas and Projects."""
        registry: dict[str, str] = {}
        for folder_name in (self.areas_folder, self.projects_folder):
            scan_path = self.vault_root / folder_name
            if not scan_path.exists():
                continue
            for file_path in scan_path.rglob("*.md"):
                if _is_excluded(file_path, self.vault_root):
                    continue
                try:
                    post = frontmatter.load(file_path)
                    code = post.metadata.get("code")
                    if not code:
                        continue
                    folder = str(file_path.relative_to(self.vault_root).parent)
                    registry[folder] = code
                except Exception:
                    continue
        return registry

    def _find_expected_code(self, folder_path: str) -> str | None:
        """Find expected project code for a folder by walking up the tree."""
        path_parts = Path(folder_path).parts
        for i in range(len(path_parts), 0, -1):
            check_path = str(Path(*path_parts[:i]))
            if check_path in self._registry:
                return self._registry[check_path]
        return None

    def _validate_note(self, note: Note) -> ValidationResult | None:
        """
        Evaluate validation rules on a note. Returns ValidationResult if issues found, else None.
        Keeps rule evaluation distinct from file walking.
        """
        score = 0
        reasons: list[str] = []

        # Rule 1: Missing Frontmatter (+10)
        if not note.frontmatter.aliases and not note.frontmatter.tags:
            score += 10
            reasons.append("Missing aliases/tags")

        # Rule 2: Code Mismatch (+50)
        folder_path = str(note.path.parent)
        expected_code = self._find_expected_code(folder_path)
        if expected_code:
            stem = note.path.stem
            if not stem.startswith(expected_code):
                score += 50
                reasons.append(f"Missing Project Code: {expected_code}")

        # Rule 3: Bad Title (+20)
        if note.path.stem.lower() in BAD_TITLES:
            score += 20
            reasons.append("Generic Filename")

        if score == 0:
            return None
        return ValidationResult(path=note.path, score=score, reasons=reasons)

    def get_note(self, path: Path) -> Note | None:
        """Retrieve a note by path. Returns None if not found."""
        full_path = self._resolve_path(path)
        if not full_path.exists():
            return None
        try:
            post = frontmatter.load(full_path)
        except Exception:
            return None
        fm = _metadata_to_frontmatter(dict(post.metadata))
        rel_path = full_path.relative_to(self.vault_root)
        return Note(path=rel_path, frontmatter=fm, body=post.content or "")

    def save_note(self, path: Path, note: Note) -> None:
        """Persist a note to the given path."""
        full_path = self._resolve_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        metadata = note.frontmatter.model_dump(exclude_none=False)
        post = frontmatter.Post(note.body, **metadata)
        content = frontmatter.dumps(post)
        full_path.write_text(content, encoding="utf-8")

    def scan_vault(self) -> list[ValidationResult]:
        """Scan the vault and return validation results for files with quality issues."""
        self._registry = self._build_registry()
        results: list[ValidationResult] = []
        dirs_to_scan = [
            self.vault_root / self.projects_folder,
            self.vault_root / self.areas_folder,
        ]
        for root_dir in dirs_to_scan:
            if not root_dir.exists():
                continue
            for file_path in root_dir.rglob("*.md"):
                if _is_excluded(file_path, self.vault_root):
                    continue
                note = self.get_note(file_path.relative_to(self.vault_root))
                if note is None:
                    continue
                validation = self._validate_note(note)
                if validation is not None:
                    results.append(validation)
        return results
