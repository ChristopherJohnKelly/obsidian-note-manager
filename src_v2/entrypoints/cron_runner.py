"""Cron entry point for headless daily routine."""

import logging
import sys
from datetime import datetime
from pathlib import Path

from src_v2.config.settings import Settings
from src_v2.core.domain.models import Frontmatter, Note
from src_v2.infrastructure.file_system.adapters import ObsidianFileSystemAdapter
from src_v2.infrastructure.testing.adapters import FakeLLM
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
    llm = FakeLLM()

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
        maint = MaintenanceService(repo, llm)
        results = maint.audit_vault()
        logger.info("Audit complete: %d file(s) need attention", len(results))
        for r in results[:10]:
            logger.info("  %s (score=%d): %s", r.path, r.score, ", ".join(r.reasons))
        task2_ok = True
    except Exception as e:
        logger.exception("Audit failed: %s", e)

    if not task1_ok and not task2_ok:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
