"""Test adapters for unit testing."""

import frontmatter
from pathlib import Path

from src_v2.core.domain.models import CodeRegistryEntry, Note, ValidationResult
from src_v2.core.interfaces.ports import LLMProvider, VaultRepository


class MockVaultAdapter(VaultRepository):
    """In-memory VaultRepository for unit tests."""

    def __init__(
        self,
        *,
        initial_scan_results: list[ValidationResult] | None = None,
        initial_code_entries: list[CodeRegistryEntry] | None = None,
        initial_skeleton: str = "",
    ) -> None:
        self.files: dict[Path, Note] = {}
        self._raw_content: dict[Path, str] = {}
        self._scan_results: list[ValidationResult] = list(initial_scan_results or [])
        self._code_entries: list[CodeRegistryEntry] = list(initial_code_entries or [])
        self._skeleton: str = initial_skeleton

    def get_note(self, path: Path) -> Note | None:
        """Retrieve a note by path. Returns None if not found."""
        return self.files.get(path)

    def save_note(self, path: Path, note: Note) -> None:
        """Persist a note to the given path."""
        self.files[path] = note

    def scan_vault(self) -> list[ValidationResult]:
        """Return pre-configured scan results."""
        return list(self._scan_results)

    def get_code_registry_entries(self) -> list[CodeRegistryEntry]:
        """Return pre-configured code registry entries."""
        return list(self._code_entries)

    def get_skeleton(self) -> str:
        """Return pre-configured skeleton."""
        return self._skeleton

    def validate_note(self, path: Path) -> ValidationResult | None:
        """Return ValidationResult from scan results if path matches, else None."""
        for r in self._scan_results:
            if r.path == path:
                return r
        return None

    def list_note_paths_in(self, directory: Path) -> list[Path]:
        """List .md file paths in a directory."""
        all_paths = set(self.files.keys()) | set(self._raw_content.keys())
        return sorted(
            p for p in all_paths
            if p.parent == directory and p.suffix == ".md"
        )

    def read_raw(self, path: Path) -> str | None:
        """Return raw file content or None if not found."""
        if path in self._raw_content:
            return self._raw_content[path]
        if path in self.files:
            note = self.files[path]
            metadata = note.frontmatter.model_dump(exclude_none=False)
            post = frontmatter.Post(note.body, **metadata)
            return frontmatter.dumps(post)
        return None

    def delete_note(self, path: Path) -> None:
        """Delete the file at path."""
        self.files.pop(path, None)
        self._raw_content.pop(path, None)

    def add_note(self, path: Path, note: Note) -> None:
        """Helper to seed a note for testing."""
        self.files[path] = note

    def set_scan_results(self, results: list[ValidationResult]) -> None:
        """Helper to configure scan_vault output for testing."""
        self._scan_results = list(results)

    def set_code_entries(self, entries: list[CodeRegistryEntry]) -> None:
        """Helper to configure get_code_registry_entries output for testing."""
        self._code_entries = list(entries)

    def set_skeleton(self, skeleton: str) -> None:
        """Helper to configure get_skeleton output for testing."""
        self._skeleton = skeleton

    def set_raw_content(self, path: Path, content: str) -> None:
        """Helper to seed raw file content for testing (e.g. capture files)."""
        self._raw_content[path] = content


class FakeLLM(LLMProvider):
    """In-memory LLMProvider for unit tests. No API calls."""

    def generate_text(self, prompt: str) -> str:
        """Echo back the prompt."""
        return prompt

    def generate_proposal(
        self,
        instructions: str,
        body: str,
        context: str,
        skeleton: str,
    ) -> str:
        """Return a predictable proposal including body and context for verification."""
        return f"%%FILE: proposal.md%%\n---\n{body}\n---\n{context}"
