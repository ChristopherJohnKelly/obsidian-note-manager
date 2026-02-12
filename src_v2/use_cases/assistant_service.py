"""Assistant Service - The Doer (Agentic Coding)."""

import frontmatter

from src_v2.config.context_config import ContextConfig
from src_v2.core.interfaces.ports import LLMProvider, VaultRepository


class AssistantService:
    """Builds context and generates multi-file proposals for agentic coding."""

    def __init__(
        self,
        repo: VaultRepository,
        llm: LLMProvider,
        config: ContextConfig | None = None,
    ) -> None:
        self.repo = repo
        self.llm = llm
        self.config = config or ContextConfig()

    def _read_file_content(self, relative_path: str) -> str:
        """Read file content from vault. Returns empty string if not found."""
        from pathlib import Path

        note = self.repo.get_note(Path(relative_path))
        if not note:
            return ""
        metadata = note.frontmatter.model_dump(exclude_none=False)
        post = frontmatter.Post(note.body, **metadata)
        return frontmatter.dumps(post)

    def get_full_context(self) -> str:
        """
        Aggregate system instructions, tag glossary, code registry, and vault skeleton.

        Returns:
            str: Combined context string for LLM prompts.
        """
        instructions = self._read_file_content(self.config.system_instructions_path)
        glossary = self._read_file_content(self.config.tag_glossary_path)

        entries = self.repo.get_code_registry_entries()
        sorted_entries = sorted(entries, key=lambda e: e.folder)
        registry_lines = ["| Code | Name | Type | Folder |", "| :--- | :--- | :--- | :--- |"]
        for entry in sorted_entries:
            registry_lines.append(f"| {entry.code} | {entry.name} | {entry.type} | {entry.folder} |")
        registry = "\n".join(registry_lines)

        skeleton = self.repo.get_skeleton()

        return f"""
=== SYSTEM INSTRUCTIONS ===
{instructions}

=== TAG GLOSSARY ===
{glossary}

=== CODE REGISTRY ===
{registry}

=== VAULT MAP (Use these for Deep Links) ===
{skeleton}
"""

    def generate_blueprint(
        self,
        user_request: str,
        body: str | None = None,
        context: str | None = None,
        skeleton: str | None = None,
    ) -> str:
        """
        Generate a multi-file proposal from a user request.

        Args:
            user_request: User instructions / intent.
            body: Raw note content. If None, uses user_request (for simple request-only calls).
            context: Full vault context. If None, uses get_full_context().
            skeleton: Vault skeleton. If None, uses empty (skeleton is typically in context).

        Returns:
            str: Raw LLM response with %%FILE%% markers.
        """
        if context is None:
            context = self.get_full_context()
        if skeleton is None:
            skeleton = ""
        if body is None:
            body = user_request

        return self.llm.generate_proposal(
            instructions=user_request,
            body=body,
            context=context,
            skeleton=skeleton,
        )
