"""Unit tests for copilot_ui.temporal_client.CopilotTemporalClient."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from temporalio.client import Client

from apps.copilot_ui.temporal_client import CopilotTemporalClient
from packages.shared.workflow_names import COPILOT_SESSION_WORKFLOW, QUEUE_DEFAULT, QRY_GET_HISTORY
from packages.shared.models import ChatMessage


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


async def test_send_user_message_signals_receive_message_with_user_role():
    """CopilotTemporalClient.send_user_message signals SIG_RECEIVE_MESSAGE on
    workflow handle with user-role payload containing the message.
    """
    # Setup
    mock_client = MagicMock(spec=Client)
    mock_handle = MagicMock()
    mock_handle.signal = AsyncMock()
    mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)

    client = CopilotTemporalClient(mock_client)

    # Execute
    await client.send_user_message("copilot-session-abc", "hello")

    # Assert get_workflow_handle was called with the session id
    assert mock_client.get_workflow_handle.call_args.args == ("copilot-session-abc",)

    # Assert signal was called once
    assert mock_handle.signal.await_count == 1

    # Assert signal was called with correct signal name and payload
    call_args = mock_handle.signal.call_args
    assert call_args.args[0] == "SIG_RECEIVE_MESSAGE"
    assert call_args.args[1] == {"role": "user", "content": "hello"}


async def test_get_chat_history_returns_list_of_chat_messages():
    """CopilotTemporalClient.get_chat_history queries QRY_GET_HISTORY and
    deserializes dicts into list[ChatMessage].
    """
    # Setup
    mock_client = MagicMock(spec=Client)
    mock_handle = MagicMock()
    mock_handle.query = AsyncMock(return_value=[
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello back"}
    ])
    mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)

    client = CopilotTemporalClient(mock_client)

    # Execute
    result = await client.get_chat_history("copilot-session-abc")

    # Assert get_workflow_handle was called with the session id
    assert mock_client.get_workflow_handle.call_args.args == ("copilot-session-abc",)

    # Assert query was called once
    assert mock_handle.query.await_count == 1

    # Assert query was called with the correct query name
    call_args = mock_handle.query.call_args
    assert call_args.args[0] == QRY_GET_HISTORY

    # Assert the result is a list of ChatMessage objects
    assert len(result) == 2
    assert all(isinstance(m, ChatMessage) for m in result)

    # Assert the messages have the correct values
    assert result[0].role == "user" and result[0].content == "hi"
    assert result[1].role == "assistant" and result[1].content == "hello back"
