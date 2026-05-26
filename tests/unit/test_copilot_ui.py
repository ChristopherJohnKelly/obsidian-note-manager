"""Unit tests for copilot_ui.temporal_client.CopilotTemporalClient."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from temporalio.client import Client

from apps.copilot_ui.temporal_client import CopilotTemporalClient
from packages.shared.workflow_names import COPILOT_SESSION_WORKFLOW, QUEUE_DEFAULT


pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_temporal_client():
    """Create a mock Temporal client with spec matching temporalio.client.Client.

    The mock has start_workflow as an AsyncMock that returns a workflow handle
    with an id attribute.
    """
    mock_client = MagicMock(spec=Client)
    mock_handle = MagicMock()
    mock_handle.id = "copilot-session-abc"
    mock_client.start_workflow = AsyncMock(return_value=mock_handle)
    return mock_client


async def test_start_copilot_session_uses_queue_default_and_returns_id(mock_temporal_client):
    """CopilotTemporalClient.start_copilot_session starts workflow on QUEUE_DEFAULT
    with deterministic id and passes vault_path in args, returning the workflow id.
    """
    client = CopilotTemporalClient(mock_temporal_client)

    result = await client.start_copilot_session(
        session_id="abc",
        vault_path="/vault"
    )

    # Assert start_workflow was called exactly once
    assert mock_temporal_client.start_workflow.await_count == 1

    # Inspect the call arguments
    call_args = mock_temporal_client.start_workflow.call_args

    # First positional argument should be the workflow type name (string)
    assert call_args[0][0] == COPILOT_SESSION_WORKFLOW

    # Keyword arguments should contain task_queue, id, and args
    kwargs = call_args[1]
    assert kwargs["task_queue"] == QUEUE_DEFAULT
    assert kwargs["id"] == "copilot-session-abc"
    assert kwargs["args"] == [{"vault_path": "/vault"}]

    # The method should return the workflow id
    assert result == "copilot-session-abc"
