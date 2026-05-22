"""Tests for the trigger module CLI."""
import pytest
from unittest.mock import AsyncMock
from apps.github_runner import trigger


@pytest.fixture(autouse=True)
def reset_client():
    """Reset the global client after each test."""
    yield
    trigger.configure_client(None)


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


def test_nightwatchman_workflow_starts_with_mock_client():
    """Test that NightWatchmanWorkflow is started via injected mock client."""
    mock_client = AsyncMock()

    trigger.configure_client(mock_client)

    exit_code = trigger.main(["--workflow", "NightWatchmanWorkflow"])

    assert exit_code == 0
    # Assert that start_workflow was awaited with the workflow name as first positional arg
    mock_client.start_workflow.assert_called_once()
    call_args = mock_client.start_workflow.call_args
    assert call_args[0][0] == "NightWatchmanWorkflow"


def test_filer_ingestion_workflow_starts_with_source_path():
    """Test that FilerIngestionWorkflow is started with correct input including source_path."""
    mock_client = AsyncMock()

    trigger.configure_client(mock_client)

    source_path = "00. Inbox/0. Capture/note.md"
    exit_code = trigger.main(["--workflow", "FilerIngestionWorkflow", "--source-path", source_path])

    assert exit_code == 0
    # Assert that start_workflow was called
    mock_client.start_workflow.assert_called_once()
    call_args = mock_client.start_workflow.call_args
    assert call_args[0][0] == "FilerIngestionWorkflow"
    # Check that the input object has the correct source_path
    input_obj = call_args[0][1]
    assert input_obj.source_path == source_path
