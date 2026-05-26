"""Unit tests for copilot_ui.temporal_client.CopilotTemporalClient."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from temporalio.client import Client

from apps.copilot_ui.temporal_client import CopilotTemporalClient
from packages.shared.workflow_names import COPILOT_SESSION_WORKFLOW, QUEUE_DEFAULT, QRY_GET_HISTORY, SIG_RECEIVE_MESSAGE
from packages.shared.models import ChatMessage, FilingProposal


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
    assert call_args.args[0] == SIG_RECEIVE_MESSAGE
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


async def test_list_pending_filer_proposals_returns_id_and_filing_proposal_tuples():
    """CopilotTemporalClient.list_pending_filer_proposals filters by status
    awaiting_approval and returns list of (workflow_id, FilingProposal) tuples.
    """
    from types import SimpleNamespace

    async def _async_iter(items):
        """Helper to create an async iterator from a list."""
        for item in items:
            yield item

    # Setup
    mock_client = MagicMock(spec=Client)

    # Create fake workflow execution objects
    wf1 = SimpleNamespace(id="filer-1")
    wf2 = SimpleNamespace(id="filer-2")

    # Mock list_workflows to return async iterator
    mock_client.list_workflows = MagicMock(return_value=_async_iter([wf1, wf2]))

    # Create mock handles
    mock_handle_1 = MagicMock()
    mock_handle_1.query = AsyncMock(side_effect=[
        "awaiting_approval",
        {
            "source_path": "/inbox/a.md",
            "proposed_path": "/areas/a.md",
            "proposed_frontmatter": {},
            "reasoning": "r1"
        }
    ])

    mock_handle_2 = MagicMock()
    mock_handle_2.query = AsyncMock(side_effect=[
        "drafting",
        None
    ])

    mock_client.get_workflow_handle = MagicMock(side_effect=[mock_handle_1, mock_handle_2])

    client = CopilotTemporalClient(mock_client)

    # Execute
    result = await client.list_pending_filer_proposals()

    # Assert list_workflows query string
    call_args = mock_client.list_workflows.call_args
    query_string = call_args.args[0]
    assert "WorkflowType = 'FilerIngestionWorkflow'" in query_string
    assert "ExecutionStatus = 'Running'" in query_string

    # Assert result
    assert len(result) == 1
    assert result[0][0] == "filer-1"
    assert isinstance(result[0][1], FilingProposal)
    assert str(result[0][1].source_path) == "/inbox/a.md"
    assert result[0][1].reasoning == "r1"


@pytest.mark.parametrize("approved,expected_signal", [
    (True, "approve"),
    (False, "reject"),
])
async def test_send_filer_decision_signals_approve_or_reject(approved, expected_signal):
    """CopilotTemporalClient.send_filer_decision signals 'approve' when
    approved=True, or 'reject' when approved=False.
    """
    # Setup
    mock_client = MagicMock(spec=Client)
    mock_handle = MagicMock()
    mock_handle.signal = AsyncMock()
    mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)

    client = CopilotTemporalClient(mock_client)

    # Execute
    await client.send_filer_decision("filer-1", approved=approved)

    # Assert get_workflow_handle was called with the workflow id
    assert mock_client.get_workflow_handle.call_args.args == ("filer-1",)

    # Assert signal was called once with the expected signal
    assert mock_handle.signal.await_count == 1
    call_args = mock_handle.signal.call_args
    assert call_args.args[0] == expected_signal


def test_requirements_has_no_vault_or_llm_dependencies():
    """apps/copilot_ui/requirements.txt should declare chainlit+temporalio+pydantic
    and must not include gitpython/google-generativeai/frontmatter.
    """
    from pathlib import Path

    text = Path("apps/copilot_ui/requirements.txt").read_text().lower()

    # Assert forbidden packages are not present
    for forbidden in ["gitpython", "google-generativeai", "frontmatter"]:
        assert forbidden not in text, f"Found forbidden package: {forbidden}"

    # Assert required packages are present
    assert "chainlit" in text, "chainlit not found in requirements.txt"
    assert "temporalio" in text, "temporalio not found in requirements.txt"
    assert "pydantic" in text, "pydantic not found in requirements.txt"


def test_app_py_imports_are_clean_temporal_client_only():
    """app.py imports only from temporal_client, no gitpython/google.generativeai/frontmatter."""
    from pathlib import Path

    text = Path("apps/copilot_ui/app.py").read_text()

    # Forbidden substrings (case-insensitive check)
    text_lower = text.lower()
    for forbidden in ["import gitpython", "import google.generativeai", "import frontmatter"]:
        assert forbidden not in text_lower, f"Forbidden import found: {forbidden}"

    # Required imports
    assert "import chainlit" in text, "Missing: import chainlit"

    # Check for temporal_client import (either absolute or relative)
    assert ("from apps.copilot_ui.temporal_client import" in text or
            "from .temporal_client import" in text), \
        "Missing: from apps.copilot_ui.temporal_client import or from .temporal_client import"

    assert "CopilotTemporalClient(" in text, "Missing: CopilotTemporalClient("


def test_app_py_implements_lifecycle_and_polling():
    """app.py has lifecycle decorators, polling loop, reconnect logic, real Client.connect."""
    from pathlib import Path
    import re

    text = Path("apps/copilot_ui/app.py").read_text()

    # Required decorators
    assert "@cl.on_chat_start" in text, "Missing: @cl.on_chat_start"
    assert "@cl.on_message" in text, "Missing: @cl.on_message"
    assert "@cl.action_callback" in text, "Missing: @cl.action_callback"

    # Required function calls
    required_calls = [
        "start_copilot_session(",
        "send_user_message(",
        "get_chat_history(",
        "list_pending_filer_proposals(",
        "send_filer_decision("
    ]
    for func in required_calls:
        assert func in text, f"Missing call to {func}"

    # Required: polling loop with while and get_chat_history (regex check)
    polling_pattern = r"while\s+.*:\s*\n(?:.|\n)*?get_chat_history"
    assert re.search(polling_pattern, text, re.DOTALL), \
        "Missing polling loop pattern (while ... get_chat_history)"

    # Required: reconnect logic - check for workflow_id session lookup
    assert ('cl.user_session.get("workflow_id"' in text or
            "cl.user_session.get('workflow_id'" in text), \
        "Missing: cl.user_session.get(\"workflow_id\") for reconnect check"

    # Required: describe/status check for existing workflow (common patterns)
    assert (".describe(" in text or
            "describe_workflow(" in text or
            "get_workflow_status" in text or
            "handle.describe" in text), \
        "Missing: describe() or status check for existing workflow handle"

    # Required: real Client.connect
    assert "Client.connect(" in text, "Missing: Client.connect("


def test_dockerfile_exists():
    """Dockerfile exists at apps/copilot_ui/Dockerfile with FROM line."""
    from pathlib import Path

    dockerfile_path = Path("apps/copilot_ui/Dockerfile")
    assert dockerfile_path.exists(), "Dockerfile does not exist at apps/copilot_ui/Dockerfile"

    text = dockerfile_path.read_text()
    assert len(text) > 0, "Dockerfile is empty"
    assert "FROM" in text, "Dockerfile missing FROM instruction"
