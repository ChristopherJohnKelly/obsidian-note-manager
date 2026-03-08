"""Filer Service - Execute approved proposals (librarian: file) from Review Queue."""

from pathlib import Path

import frontmatter

from src_v2.core.domain.models import Frontmatter, Note
from src_v2.core.interfaces.ports import VaultRepository
from src_v2.core.response_parser import parse_proposal
from src_v2.core.vault_utils import get_safe_path


def _metadata_to_frontmatter(metadata: dict) -> Frontmatter:
    """Convert raw metadata dict to Frontmatter model."""
    return Frontmatter.model_validate(metadata)


class FilerService:
    """Executes proposals with librarian: file by creating files and deleting proposals."""

    def __init__(
        self,
        repo: VaultRepository,
        *,
        review_dir: str,
        vault_root: Path,
    ) -> None:
        self.repo = repo
        self.review_dir = Path(review_dir)
        self.vault_root = Path(vault_root)

    def file_approved_notes(self) -> int:
        """
        Execute proposals with librarian: file.

        Parses proposal notes, extracts files via response parser, writes each file
        with collision handling, and deletes the proposal after successful execution.

        Returns:
            Total number of new files created.
        """
        paths = self.repo.list_note_paths_in(self.review_dir)
        if not paths:
            return 0

        files_created_total = 0

        for prop_path in paths:
            note = self.repo.get_note(prop_path)
            if note is None:
                continue

            librarian = note.frontmatter.model_dump().get("librarian")
            if librarian != "file":
                continue

            parsed = parse_proposal(note.body)
            if not parsed["files"]:
                continue

            target_file = note.frontmatter.model_dump().get("target-file")
            is_maintenance_fix = target_file is not None
            original_handled = False
            files_created_this_proposal = 0

            for file_data in parsed["files"]:
                rel_path = file_data["path"]
                content = file_data["content"]

                if ".." in rel_path or rel_path.startswith("/"):
                    continue

                full_target_path = self.vault_root / rel_path

                if is_maintenance_fix:
                    is_rename = target_file and target_file != rel_path

                    if is_rename and not original_handled:
                        if self.repo.read_raw(Path(target_file)) is not None:
                            self.repo.delete_note(Path(target_file))
                        original_handled = True
                        safe_full = get_safe_path(full_target_path)
                    elif not is_rename and not original_handled:
                        safe_full = full_target_path
                        original_handled = True
                    else:
                        safe_full = get_safe_path(full_target_path)
                else:
                    safe_full = get_safe_path(full_target_path)

                safe_rel = safe_full.relative_to(self.vault_root)
                try:
                    post = frontmatter.loads(content)
                except Exception:
                    post = frontmatter.Post(content, **{})
                fm = _metadata_to_frontmatter(dict(post.metadata))
                file_note = Note(path=safe_rel, frontmatter=fm, body=post.content or "")
                self.repo.save_note(safe_rel, file_note)
                files_created_this_proposal += 1
                files_created_total += 1

            if files_created_this_proposal > 0:
                self.repo.delete_note(prop_path)

        return files_created_total
