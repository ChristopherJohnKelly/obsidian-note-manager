"""Tests for the trigger module CLI."""
import pytest
from apps.github_runner import trigger


def test_unknown_workflow_returns_1_with_stderr_message(capsys):
    """Test that unknown --workflow argument returns 1 with error message to stderr."""
    exit_code = trigger.main(["--workflow", "UnknownWorkflow"])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Unknown workflow: UnknownWorkflow" in captured.err


def test_vault_manager_workflow_not_in_workflows():
    """Test that VaultManagerWorkflow is not exported in WORKFLOWS dict."""
    # Ensure VaultManagerWorkflow is not a key in the WORKFLOWS dict
    assert "VaultManagerWorkflow" not in trigger.WORKFLOWS
    # Also ensure the constant itself is not exported at module level
    assert not hasattr(trigger, "VAULT_MANAGER_WORKFLOW")
