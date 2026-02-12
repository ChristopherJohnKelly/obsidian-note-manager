"""Maintenance Service - The Night Watchman."""

from pathlib import Path

import frontmatter

from src_v2.core.domain.models import ValidationResult
from src_v2.core.interfaces.ports import LLMProvider, VaultRepository


class MaintenanceService:
    """Audits the vault for quality issues and generates fix proposals."""

    def __init__(self, repo: VaultRepository, llm: LLMProvider) -> None:
        self.repo = repo
        self.llm = llm

    def audit_vault(self) -> list[ValidationResult]:
        """
        Return files that need attention (score > 0), sorted by score descending.

        Returns:
            list[ValidationResult]: Dirty files, highest score first.
        """
        all_results = self.repo.scan_vault()
        dirty = [r for r in all_results if r.score > 0]
        return sorted(dirty, key=lambda x: x.score, reverse=True)

    def generate_fix(self, path: Path, reasons: list[str], context: str) -> str:
        """
        Load a note, build a maintenance prompt, and return the LLM proposal.

        Does not save the proposal; that is an orchestration concern.

        Args:
            path: Path to the note (relative to vault root).
            reasons: Detected issues from audit_vault (e.g. ["Missing aliases/tags", "Generic Filename"]).
            context: Full vault context (system instructions, glossary, code registry, skeleton).

        Returns:
            str: Raw LLM response with %%FILE%% markers.

        Raises:
            FileNotFoundError: If the note is not found.
        """
        note = self.repo.get_note(path)
        if not note:
            raise FileNotFoundError(f"Note {path} not found")

        metadata = note.frontmatter.model_dump(exclude_none=False)
        post = frontmatter.Post(note.body, **metadata)
        raw_content = frontmatter.dumps(post)

        instructions = (
            f"MAINTENANCE MODE. This note has failed quality checks.\n"
            f"Detected Issues: {', '.join(reasons)}.\n\n"
            f"Task:\n"
            f"1. Fix the Frontmatter (add missing aliases, tags, or other required metadata).\n"
            f"2. Rename the file if it violates Project Code conventions (filename should start with the expected project code).\n"
            f"3. Do NOT rewrite the body text unless essential for formatting or fixing critical errors.\n"
            f"4. Preserve all existing content and structure.\n"
            f"5. Output the result using the %%FILE%% schema with the corrected path if renaming is needed."
        )

        return self.llm.generate_proposal(
            instructions=instructions,
            body=raw_content,
            context=context,
            skeleton="",  # Skeleton is already in context
        )
