"""Unit tests for cron_runner main() fix loop."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src_v2.core.domain.models import ValidationResult
from src_v2.entrypoints.cron_runner import main



def _valid_proposal(path: str) -> str:
    """Return a parseable %%FILE%% proposal for the given path."""
    return f"""%%FILE: {path}%%
---
title: Fixed
aliases: [Fixed Note]
tags: [project]
---
Body content.
"""


class TestCronRunnerFixLoop:
    """Tests for the Night Watchman fix loop in cron_runner.main()."""

    @pytest.fixture(autouse=True)
    def _patch_dependencies(self, tmp_path):
        """Patch Settings, GeminiAdapter, and file system for isolated tests."""
        (tmp_path / "99. System" / "Logs").mkdir(parents=True)
        mock_settings = MagicMock()
        mock_settings.return_value.vault_root = tmp_path
        mock_settings.return_value.gemini_api_key = "test-key"
        mock_settings.return_value.log_level = "INFO"
        mock_settings.return_value.registry_output_path = "99. System/Registry.md"
        mock_repo = MagicMock()
        mock_repo.save_note = MagicMock()
        mock_repo.delete_note = MagicMock()
        mock_repo.get_code_registry_entries = MagicMock(return_value=[])

        with (
            patch("src_v2.entrypoints.cron_runner.Settings", mock_settings),
            patch("src_v2.entrypoints.cron_runner.GeminiAdapter"),
            patch("src_v2.entrypoints.cron_runner.ObsidianFileSystemAdapter") as mock_adapter_cls,
        ):
            mock_adapter_cls.return_value = mock_repo
            yield {"adapter": mock_adapter_cls, "repo": mock_repo}

    def test_limit_fix_loop_executes_exactly_10_times(self, _patch_dependencies):
        """If audit_vault returns 15 offenders, fix_file is called exactly 10 times."""
        fifteen_offenders = [
            ValidationResult(path=Path(f"20. Projects/Pepsi/file_{i}.md"), score=10, reasons=["Missing tags"])
            for i in range(15)
        ]

        with patch("src_v2.entrypoints.cron_runner.MaintenanceService") as MockMaint:
            mock_maint = MagicMock()
            MockMaint.return_value = mock_maint
            mock_maint.audit_vault.return_value = fifteen_offenders
            mock_maint.fix_file.side_effect = [
                _valid_proposal(f"20. Projects/Pepsi/file_{i}.md") for i in range(10)
            ]

            result = main()

        assert result == 0
        assert mock_maint.fix_file.call_count == 10

    def test_fault_tolerance_continues_after_fix_file_exception(self, _patch_dependencies):
        """If fix_file raises on one file, loop continues and runner exits 0."""
        mock_repo = _patch_dependencies["repo"]
        ten_offenders = [
            ValidationResult(path=Path(f"20. Projects/Pepsi/file_{i}.md"), score=10, reasons=["Missing tags"])
            for i in range(10)
        ]

        call_count = 0

        def fix_file_side_effect(path):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise ValueError("Bad LLM response")
            return _valid_proposal(str(path))

        with patch("src_v2.entrypoints.cron_runner.MaintenanceService") as MockMaint:
            mock_maint = MagicMock()
            MockMaint.return_value = mock_maint
            mock_maint.audit_vault.return_value = ten_offenders
            mock_maint.fix_file.side_effect = fix_file_side_effect

            result = main()

        assert result == 0
        assert mock_maint.fix_file.call_count == 10
        # 1 save for registry update + 9 for successful fixes (1 failed)
        assert mock_repo.save_note.call_count == 10

    def test_empty_state_never_calls_fix_file(self, _patch_dependencies):
        """If audit_vault returns 0 offenders, fix_file is never called."""
        with patch("src_v2.entrypoints.cron_runner.MaintenanceService") as MockMaint:
            mock_maint = MagicMock()
            MockMaint.return_value = mock_maint
            mock_maint.audit_vault.return_value = []

            result = main()

        assert result == 0
        mock_maint.fix_file.assert_not_called()
