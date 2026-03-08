"""Unit tests for ingest_runner entry point."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src_v2.entrypoints.ingest_runner import main


class TestIngestRunner:
    """Tests for ingest_runner.main()."""

    @patch("src_v2.entrypoints.ingest_runner.GeminiAdapter")
    @patch("src_v2.entrypoints.ingest_runner.ObsidianFileSystemAdapter")
    @patch("src_v2.entrypoints.ingest_runner.Settings")
    def test_main_returns_zero_on_success(
        self,
        mock_settings_cls: MagicMock,
        mock_adapter_cls: MagicMock,
        mock_gemini_cls: MagicMock,
    ) -> None:
        mock_settings = MagicMock()
        mock_settings.vault_root = Path("/tmp/vault")
        mock_settings.gemini_api_key = "test-key"
        mock_settings.review_dir = "00. Inbox/1. Review Queue"
        mock_settings.capture_dir = "00. Inbox/0. Capture"
        mock_settings.log_level = "INFO"
        mock_settings_cls.return_value = mock_settings

        mock_repo = MagicMock()
        mock_adapter_cls.return_value = mock_repo

        with patch("src_v2.entrypoints.ingest_runner.FilerService") as mock_filer_cls:
            with patch("src_v2.entrypoints.ingest_runner.IngestionService") as mock_ingest_cls:
                mock_filer = MagicMock()
                mock_filer.file_approved_notes.return_value = 0
                mock_filer_cls.return_value = mock_filer

                mock_ingest = MagicMock()
                mock_ingest.run.return_value = MagicMock(
                    processed_count=0, success=True
                )
                mock_ingest_cls.return_value = mock_ingest

                exit_code = main()

        assert exit_code == 0
        mock_filer.file_approved_notes.assert_called_once()
        mock_ingest.run.assert_called_once()

    @patch("src_v2.entrypoints.ingest_runner.GeminiAdapter")
    @patch("src_v2.entrypoints.ingest_runner.ObsidianFileSystemAdapter")
    @patch("src_v2.entrypoints.ingest_runner.Settings")
    def test_main_returns_zero_when_empty_capture(
        self,
        mock_settings_cls: MagicMock,
        mock_adapter_cls: MagicMock,
        mock_gemini_cls: MagicMock,
    ) -> None:
        mock_settings = MagicMock()
        mock_settings.vault_root = Path("/tmp/vault")
        mock_settings.gemini_api_key = "test-key"
        mock_settings.review_dir = "00. Inbox/1. Review Queue"
        mock_settings.capture_dir = "00. Inbox/0. Capture"
        mock_settings.log_level = "INFO"
        mock_settings_cls.return_value = mock_settings

        mock_repo = MagicMock()
        mock_adapter_cls.return_value = mock_repo

        with patch("src_v2.entrypoints.ingest_runner.FilerService") as mock_filer_cls:
            with patch("src_v2.entrypoints.ingest_runner.IngestionService") as mock_ingest_cls:
                mock_filer = MagicMock()
                mock_filer.file_approved_notes.return_value = 0
                mock_filer_cls.return_value = mock_filer

                mock_ingest = MagicMock()
                mock_ingest.run.return_value = MagicMock(
                    processed_count=0, success=True
                )
                mock_ingest_cls.return_value = mock_ingest

                exit_code = main()

        assert exit_code == 0

    @patch("src_v2.entrypoints.ingest_runner.GeminiAdapter")
    @patch("src_v2.entrypoints.ingest_runner.Settings")
    def test_main_returns_one_when_gemini_api_key_missing(
        self,
        mock_settings_cls: MagicMock,
        mock_gemini_cls: MagicMock,
    ) -> None:
        mock_settings = MagicMock()
        mock_settings.vault_root = Path("/tmp/vault")
        mock_settings.gemini_api_key = ""
        mock_settings.log_level = "INFO"
        mock_settings_cls.return_value = mock_settings

        mock_gemini_cls.side_effect = ValueError("GEMINI_API_KEY not set")

        exit_code = main()

        assert exit_code == 1
