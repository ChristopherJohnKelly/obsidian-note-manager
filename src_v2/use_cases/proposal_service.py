"""Proposal Service - Agent 2 (The Proposer). Generates markdown drafts from chat history."""

import os
import time
from pathlib import Path

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from src_v2.core.domain.models import Frontmatter, Note
from src_v2.core.interfaces.ports import VaultRepository
from src_v2.core.response_parser import parse_proposal
from src_v2.core.vault_utils import get_safe_path

PROPOSER_SYSTEM_PROMPT = """You are an Obsidian Proposer. Your role is to draft markdown file updates based on a conversation about a vault area.

INPUT:
1. Chat history (user and assistant messages about the vault area)
2. File contents from the active area (for context)

OUTPUT FORMAT:
You must output a single text blob using these delimiters:

%%EXPLANATION%%
(Short reasoning: what you are proposing and why)

%%FILE: <vault_relative_path>/<filename>.md%%
---
title: <Title>
tags: [<tag1>, <tag2>]
folder: <folder_path>
---
<Content with [[Deep Links]] to existing notes if applicable>

%%FILE: <another_path>/<another_file>.md%%
...

RULES:
1. Always use the %%FILE: path%% delimiter.
2. Use vault-relative paths (e.g. "20. Projects/Alpha/NewDoc.md"), never relative paths like "./foo.md".
3. Ensure frontmatter is valid YAML.
4. Do NOT invent links. Only link to items that exist in the vault.
5. Create one or more %%FILE%% blocks based on what was discussed in the conversation.
6. Paths must be within the vault structure (e.g. 20. Projects, 30. Areas)."""


def _is_safe_path(path: str) -> bool:
    """Reject path traversal and absolute paths."""
    if not path or not path.strip():
        return False
    p = path.strip()
    if ".." in p or p.startswith("/"):
        return False
    return True


class ProposalService:
    """Agent 2: Generates markdown proposals from chat history and writes to Review Queue."""

    def __init__(
        self,
        repo: VaultRepository,
        *,
        vault_root: Path,
        review_dir: str,
        api_key: str | None = None,
        model_name: str = "gemini-2.0-flash",
    ) -> None:
        self.repo = repo
        self.vault_root = Path(vault_root)
        self.review_dir = Path(review_dir)
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY required for ProposalService")
        genai.configure(api_key=key)
        self.model_name = model_name

    def _load_area_context(self, active_area: str) -> str:
        """Load file contents from active_area for LLM context."""
        area_path = Path(active_area)
        paths = self.repo.list_note_paths_in(area_path)
        if not paths:
            return "(No files found in this area.)"

        parts: list[str] = []
        for p in paths[:20]:  # Limit to avoid token overflow
            content = self.repo.read_raw(p)
            if content:
                parts.append(f"--- FILE: {p} ---\n{content}")
        return "\n\n".join(parts) if parts else "(No readable files.)"

    def _format_chat_history(self, chat_history: list[dict]) -> str:
        """Convert OpenAI-format chat history to a readable string."""
        lines: list[str] = []
        for msg in chat_history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    c.get("text", str(c)) for c in content if isinstance(c, dict)
                )
            lines.append(f"[{role}]: {content}")
        return "\n".join(lines)

    def generate_draft(self, chat_history: list[dict], active_area: str) -> str:
        """
        Generate a markdown proposal from chat history and write to Review Queue.

        Args:
            chat_history: List of {"role": "user"|"assistant", "content": "..."}.
            active_area: Vault directory that was discussed (e.g. "20. Projects").

        Returns:
            Success message including the written path, or error message.
        """
        if not chat_history:
            return "No chat history to draft from. Please have a conversation first."

        area_context = self._load_area_context(active_area)
        history_str = self._format_chat_history(chat_history)

        user_prompt = f"""=== CHAT HISTORY ===
{history_str}

=== FILE CONTENTS FROM ACTIVE AREA ({active_area}) ===
{area_context}

Based on this conversation, generate a markdown file proposal. Output using the %%FILE%% format."""

        model = genai.GenerativeModel(
            self.model_name,
            system_instruction=PROPOSER_SYSTEM_PROMPT,
        )
        config = GenerationConfig(
            temperature=0.0,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
        )

        try:
            response = model.generate_content(
                user_prompt,
                generation_config=config,
            )
            raw_output = response.text if response and response.text else ""
        except Exception as e:
            return f"LLM error: {e}"

        if not raw_output or not raw_output.strip():
            return "The model produced no output. Please try again."

        parsed = parse_proposal(raw_output)

        # Filter out unsafe paths
        safe_files = [
            f for f in parsed["files"]
            if _is_safe_path(f["path"])
        ]
        if not safe_files:
            return "No valid file paths in the proposal (path traversal blocked)."

        # Build proposal filename and path
        timestamp = int(time.time())
        base_name = f"copilot-draft-{timestamp}"
        review_path = self.vault_root / self.review_dir / f"{base_name}.md"
        safe_review_path = get_safe_path(review_path)
        rel_review_path = safe_review_path.relative_to(self.vault_root)

        # Ensure librarian: file in frontmatter
        frontmatter_dict = {"librarian": "file"}
        fm = Frontmatter.model_validate(frontmatter_dict)
        note = Note(
            path=rel_review_path,
            frontmatter=fm,
            body=raw_output,
        )

        self.repo.save_note(rel_review_path, note)
        return f"Draft saved to {rel_review_path}. Please review in Obsidian."
