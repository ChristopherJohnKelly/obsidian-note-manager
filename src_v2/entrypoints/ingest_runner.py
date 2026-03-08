"""Ingestion entry point for headless Capture-to-Review-Queue pipeline."""

import logging
import sys
from datetime import datetime
from pathlib import Path

from src_v2.config.settings import Settings
from src_v2.infrastructure.file_system.adapters import ObsidianFileSystemAdapter
from src_v2.infrastructure.llm.adapters import GeminiAdapter
from src_v2.use_cases.filer_service import FilerService
from src_v2.use_cases.ingestion_service import IngestionService


def _setup_logging(settings: Settings) -> logging.Logger:
    """Configure logging to vault Logs directory and stdout for GitHub Actions visibility."""
    log_dir = settings.vault_root / "99. System" / "Logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"ingest_{datetime.now().strftime('%Y-%m-%d')}.log"

    logger = logging.getLogger("ingest_runner")
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def main() -> int:
    settings = Settings()
    logger = _setup_logging(settings)

    try:
        llm = GeminiAdapter(api_key=settings.gemini_api_key)
    except ValueError as e:
        logger.error("LLM init failed: %s", e)
        return 1

    repo = ObsidianFileSystemAdapter(settings.vault_root)

    try:
        filer = FilerService(
            repo,
            review_dir=settings.review_dir,
            vault_root=settings.vault_root,
        )
        filed_count = filer.file_approved_notes()
        logger.info("Filed %d note(s) from Review Queue", filed_count)

        ingestion = IngestionService(
            repo,
            llm,
            capture_dir=settings.capture_dir,
            review_dir=settings.review_dir,
            vault_root=settings.vault_root,
        )
        result = ingestion.run()
        logger.info("Ingested %d note(s) from Capture", result.processed_count)

        if not result.success:
            logger.error("Ingestion failed")
            return 1

        return 0
    except Exception as e:
        logger.exception("Pipeline failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
