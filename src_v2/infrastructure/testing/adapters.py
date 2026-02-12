"""Test adapters for unit testing."""

from pathlib import Path

from src_v2.core.domain.models import Note, ValidationResult
from src_v2.core.interfaces.ports import VaultRepository


class MockVaultAdapter(VaultRepository):
    """In-memory VaultRepository for unit tests."""

    def __init__(
        self,
        *,
        initial_scan_results: list[ValidationResult] | None = None,
    ) -> None:
        self.files: dict[Path, Note] = {}
        self._scan_results: list[ValidationResult] = list(initial_scan_results or [])

    def get_note(self, path: Path) -> Note | None:
        """Retrieve a note by path. Returns None if not found."""
        return self.files.get(path)

    def save_note(self, path: Path, note: Note) -> None:
        """Persist a note to the given path."""
        self.files[path] = note

    def scan_vault(self) -> list[ValidationResult]:
        """Return pre-configured scan results."""
        return list(self._scan_results)

    def add_note(self, path: Path, note: Note) -> None:
        """Helper to seed a note for testing."""
        self.files[path] = note

    def set_scan_results(self, results: list[ValidationResult]) -> None:
        """Helper to configure scan_vault output for testing."""
        self._scan_results = list(results)
