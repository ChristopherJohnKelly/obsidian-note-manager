"""Ingestion Service - Capture to Review Queue pipeline."""

import re
import time
from dataclasses import dataclass
from pathlib import Path

import frontmatter

from src_v2.core.domain.models import Frontmatter, Note
from src_v2.core.interfaces.ports import LLMProvider, VaultRepository
from src_v2.core.response_parser import parse_proposal
from src_v2.core.vault_utils import get_safe_path, sanitize_filename


@dataclass
class IngestionResult:
    """Result of running the ingestion pipeline."""

    processed_count: int
    success: bool


def _extract_instructions(content: str) -> tuple[str | None, str]:
    """Extract LLM-Instructions block from note content. Returns (instructions, cleaned_body)."""
    pattern = r"```LLM-Instructions\s*(.*?)```"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        instructions = match.group(1).strip()
        cleaned_body = re.sub(pattern, "", content, flags=re.DOTALL).strip()
        return instructions, cleaned_body
    return None, content


class IngestionService:
    """Processes capture files: read, LLM transform, save to Review Queue, delete original."""

    def __init__(
        self,
        repo: VaultRepository,
        llm: LLMProvider,
        *,
        capture_dir: str,
        review_dir: str,
        vault_root: Path,
        context_builder: "ContextBuilder | None" = None,
    ) -> None:
        self.repo = repo
        self.llm = llm
        self.capture_dir = Path(capture_dir)
        self.review_dir = Path(review_dir)
        self.vault_root = Path(vault_root)
        self._context_builder = context_builder

    def _build_context(self) -> str:
        """Build full vault context for LLM (system instructions, glossary, registry, skeleton)."""
        if self._context_builder:
            return self._context_builder.build_context()
        from src_v2.use_cases.assistant_service import AssistantService
        from src_v2.config.context_config import ContextConfig

        assistant = AssistantService(self.repo, self.llm, ContextConfig())
        return assistant.get_full_context()

    def _get_skeleton(self) -> str:
        """Get vault skeleton for LLM."""
        return self.repo.get_skeleton()

    def run(self) -> IngestionResult:
        """
        Process all capture files: read, transform via LLM, save to Review Queue, delete original.

        Returns:
            IngestionResult with processed_count and success.
        """
        paths = self.repo.list_note_paths_in(self.capture_dir)
        if not paths:
            return IngestionResult(processed_count=0, success=True)

        context = self._build_context()
        skeleton = self._get_skeleton()
        processed = 0

        for capture_path in paths:
            raw_content = self.repo.read_raw(capture_path)
            if raw_content is None:
                continue

            instructions, body = _extract_instructions(raw_content)
            if not instructions:
                instructions = "Organize this note using standard conventions."

            try:
                llm_response = self.llm.generate_proposal(
                    instructions=instructions,
                    body=body,
                    context=context,
                    skeleton=skeleton,
                )
            except Exception:
                return IngestionResult(processed_count=processed, success=False)

            parsed = parse_proposal(llm_response)
            file_paths = [f["path"] for f in parsed["files"]]
            folders = list({str(Path(p).parent) for p in file_paths if p})

            if file_paths:
                first_file = Path(file_paths[0])
                base_name = first_file.stem
            else:
                base_name = f"proposal-{int(time.time())}"

            safe_filename = sanitize_filename(base_name)
            new_filename = f"{safe_filename}.md"
            full_review_path = self.vault_root / self.review_dir / new_filename
            safe_full_path = get_safe_path(full_review_path)
            review_path = safe_full_path.relative_to(self.vault_root)

            proposal_content = f"""%%INSTRUCTIONS%%
{instructions}
---
%%ORIGINAL%%
{body}
---
{llm_response}
"""
            fm = Frontmatter.model_validate({
                "folders-to-create": folders,
                "files-to-create": file_paths,
                "librarian": "review",
            })
            note = Note(path=review_path, frontmatter=fm, body=proposal_content)

            self.repo.save_note(review_path, note)
            self.repo.delete_note(capture_path)
            processed += 1

        return IngestionResult(processed_count=processed, success=True)


class ContextBuilder:
    """Abstract context builder for injection in tests."""

    def build_context(self) -> str:
        """Build full vault context string."""
        raise NotImplementedError
