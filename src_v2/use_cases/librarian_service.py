"""Librarian Service - Knowing what is where."""

from src_v2.core.interfaces.ports import VaultRepository


class LibrarianService:
    """Generates the Code Registry Markdown table for the vault."""

    def __init__(self, repo: VaultRepository) -> None:
        self.repo = repo

    def generate_registry(self) -> str:
        """
        Generate the Markdown content for the Code Registry table.

        Scans Areas and Projects via the repo, sorts by folder, and formats as a table.

        Returns:
            str: Markdown table with columns Code | Name | Type | Folder
        """
        entries = self.repo.get_code_registry_entries()
        sorted_entries = sorted(entries, key=lambda e: e.folder)

        lines = ["| Code | Name | Type | Folder |", "| :--- | :--- | :--- | :--- |"]
        for entry in sorted_entries:
            lines.append(f"| {entry.code} | {entry.name} | {entry.type} | {entry.folder} |")
        return "\n".join(lines)
