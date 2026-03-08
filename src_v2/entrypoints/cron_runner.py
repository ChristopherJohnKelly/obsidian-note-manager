"""Cron entry point for headless daily routine."""

import logging
import sys
from datetime import datetime
from pathlib import Path

from src_v2.config.context_config import ContextConfig
from src_v2.config.settings import Settings
from src_v2.core.domain.models import Frontmatter, Note
from src_v2.core.response_parser import parse_proposal
from src_v2.core.vault_utils import note_from_raw_content
from src_v2.infrastructure.file_system.adapters import ObsidianFileSystemAdapter
from src_v2.infrastructure.llm.adapters import GeminiAdapter
from src_v2.use_cases.assistant_service import AssistantService
from src_v2.use_cases.librarian_service import LibrarianService
from src_v2.use_cases.maintenance_service import MaintenanceService


def _setup_logging(settings: Settings) -> logging.Logger:
    """Configure logging to vault Logs directory."""
    log_dir = settings.vault_root / "99. System" / "Logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"cron_{datetime.now().strftime('%Y-%m-%d')}.log"

    logger = logging.getLogger("cron_runner")
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

    return logger


def main() -> int:
    settings = Settings()
    logger = _setup_logging(settings)
    repo = ObsidianFileSystemAdapter(settings.vault_root)
        
    try:
        llm = GeminiAdapter(api_key=settings.gemini_api_key)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    task1_ok = False
    task2_ok = False

    try:
        lib = LibrarianService(repo)
        registry_content = lib.generate_registry()
        note = Note(
            path=Path(settings.registry_output_path),
            frontmatter=Frontmatter(title="Code Registry", type="system"),
            body=registry_content,
        )
        repo.save_note(Path(settings.registry_output_path), note)
        logger.info("Registry updated: %s", settings.registry_output_path)
        task1_ok = True
    except Exception as e:
        logger.exception("Registry update failed: %s", e)

    try:
        config = ContextConfig()
        assistant = AssistantService(repo, llm, config)
        maint = MaintenanceService(repo, llm, assistant_service=assistant)
        results = maint.audit_vault()
        logger.info("Audit complete: %d file(s) need attention", len(results))

        if not results:
            logger.info("No offenders to fix")
            task2_ok = True
        else:
            offenders = results[:10]
            for i, r in enumerate(offenders, 1):
                try:
                    proposal = maint.fix_file(r.path)
                    parsed = parse_proposal(proposal)
                    if not parsed["files"]:
                        logger.warning("No %%FILE%% blocks in fix for %s", r.path)
                        continue

                    file_data = parsed["files"][0]
                    new_path_str = file_data["path"]
                    content = file_data["content"]

                    if ".." in new_path_str or new_path_str.startswith("/"):
                        logger.warning("Rejected unsafe path: %s", new_path_str)
                        continue

                    new_path = Path(new_path_str)
                    note = note_from_raw_content(new_path, content)

                    if str(new_path) != str(r.path):
                        repo.delete_note(r.path)
                    repo.save_note(new_path, note)
                    logger.info("Fixed %d/%d: %s", i, len(offenders), new_path)
                except Exception as e:
                    logger.exception("Fix failed for %s: %s", r.path, e)
            task2_ok = True
    except Exception as e:
        logger.exception("Audit failed: %s", e)

    if not task1_ok and not task2_ok:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
