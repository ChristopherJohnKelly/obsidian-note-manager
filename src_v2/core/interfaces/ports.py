"""Abstract interfaces (ports) for infrastructure adapters."""

from abc import ABC, abstractmethod
from pathlib import Path

from src_v2.core.domain.models import Note, ValidationResult


class VaultRepository(ABC):
    """Abstract interface for vault storage operations."""

    @abstractmethod
    def get_note(self, path: Path) -> Note | None:
        """Retrieve a note by path. Returns None if not found."""
        ...

    @abstractmethod
    def save_note(self, path: Path, note: Note) -> None:
        """Persist a note to the given path."""
        ...

    @abstractmethod
    def scan_vault(self) -> list[ValidationResult]:
        """Scan the vault and return validation results for files with quality issues."""
        ...


class LLMProvider(ABC):
    """Abstract interface for LLM operations."""

    @abstractmethod
    def generate_text(self, prompt: str) -> str:
        """Generate text from a prompt."""
        ...

    @abstractmethod
    def generate_proposal(
        self,
        instructions: str,
        body: str,
        context: str,
        skeleton: str,
    ) -> str:
        """Generate a multi-file proposal. Returns raw LLM response with %%FILE%% markers."""
        ...
