"""E2E tests for Copilot session workflow Activities.

Tests the generate_chat_response Activity and FakeLLMProvider chat/react methods
used in the Temporal Copilot session workflow.
"""

import asyncio
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import pytest_asyncio
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from apps.vault_worker.activities.llm import (
    configure_provider,
    generate_chat_response,
)
from apps.vault_worker.workflows.copilot_session import CopilotSessionWorkflow
from packages.shared.models import ChatMessage
from tests.mocks.fake_llm import FakeLLMProvider


def test_generate_chat_response_with_fake_provider():
    """Test generate_chat_response Activity delegates to the configured provider."""
    provider = FakeLLMProvider()
    configure_provider(provider)

    messages = [ChatMessage(role="user", content="What is the capital of France?")]
    result = generate_chat_response(messages)

    assert isinstance(result, str)
    assert result == "Here is your answer."

    configure_provider(None)


def test_fake_provider_generate_react_response_tool_call():
    """Test FakeLLMProvider.generate_react_response with tool_call mode."""
    provider = FakeLLMProvider()

    result = provider.generate_react_response("tool_call")

    assert "TOOL: get_skeleton" in result
    assert "ARGS: {}" in result


def test_fake_provider_generate_react_response_direct():
    """Test FakeLLMProvider.generate_react_response without tool_call mode."""
    provider = FakeLLMProvider()

    result = provider.generate_react_response("direct")

    assert isinstance(result, str)
    assert "TOOL:" not in result


def test_fake_provider_generate_react_response_other_modes():
    """Test FakeLLMProvider.generate_react_response with arbitrary modes returns direct response."""
    provider = FakeLLMProvider()

    result = provider.generate_react_response("anything")

    assert isinstance(result, str)
    assert "TOOL:" not in result


# ---------------------------------------------------------------------------
# Copilot session workflow E2E tests
# ---------------------------------------------------------------------------

# Global event for gating the mock activity (used by ThreadPoolExecutor activities)
_mock_activity_event: threading.Event | None = None


def mock_chat_activity(messages: list[ChatMessage]) -> str:
    """Gated mock activity for generate_chat_response.

    Waits on _mock_activity_event before returning a direct response.
    This allows tests to assert on in-flight workflow state (e.g., status="thinking").
    Runs in ThreadPoolExecutor, so uses threading.Event instead of asyncio.Event.
    """
    global _mock_activity_event
    if _mock_activity_event:
        _mock_activity_event.wait()
    return "The answer is 42."


# Register the mock activity with the correct name
activity.defn(name="generate_chat_response")(mock_chat_activity)


# Stateful mock for tool-use test
_tool_use_test_call_count = 0


def mock_chat_for_tool_use(messages: list[ChatMessage]) -> str:
    """Stateful mock that returns tool_call format on first call, direct response on second.

    This mock is used to test the two-call tool-use flow:
    1. First call returns tool_call format (e.g., "TOOL: get_skeleton\nARGS: {}")
    2. Workflow dispatches the tool
    3. Tool result is appended to history
    4. Second call returns a direct string response
    """
    global _tool_use_test_call_count, _mock_activity_event
    if _mock_activity_event:
        _mock_activity_event.wait()

    _tool_use_test_call_count += 1
    if _tool_use_test_call_count == 1:
        provider = FakeLLMProvider()
        return provider.generate_react_response("tool_call")
    else:
        return "Skeleton analysis complete."


def mock_get_skeleton_activity(vault_path: str) -> str:
    """Mock for get_skeleton activity in tool-use test."""
    return "vault_structure: [notes, attachments, config.json]"


@pytest_asyncio.fixture
async def pydantic_client(temporal_client: Client) -> Client:
    """Client with pydantic_data_converter for E2E tests."""
    return Client(
        service_client=temporal_client.service_client,
        namespace=temporal_client.namespace,
        data_converter=pydantic_data_converter,
    )


async def test_copilot_session_single_turn(pydantic_client: Client):
    """CopilotSessionWorkflow single-turn E2E test.

    Tests signals, queries, and the direct ReAct response path.
    - Workflow starts in idle status
    - Signal receive_message causes thinking status
    - History accumulates user and assistant messages
    - get_status query returns current state
    - Workflow returns to idle after processing
    """
    global _mock_activity_event
    task_queue = f"test-copilot-{uuid.uuid4().hex[:8]}"

    async with Worker(
        pydantic_client,
        task_queue=task_queue,
        workflows=[CopilotSessionWorkflow],
        activities=[mock_chat_activity],
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        # Start workflow
        handle = await pydantic_client.start_workflow(
            CopilotSessionWorkflow.run,
            {"vault_path": "/test/vault", "session_id": "test-session-1"},
            id=f"copilot-test-{uuid.uuid4().hex[:8]}",
            task_queue=task_queue,
        )

        try:
            # Assert initial state: idle
            status = await handle.query(CopilotSessionWorkflow.get_status)
            assert status == "idle", f"Expected idle, got {status}"

            # Assert initial history is empty
            history = await handle.query(CopilotSessionWorkflow.get_history)
            assert len(history) == 0, f"Expected empty history, got {len(history)} items"

            # Gate the mock activity using threading.Event
            _mock_activity_event = threading.Event()

            # Signal a user message
            await handle.signal(
                CopilotSessionWorkflow.receive_message,
                {"role": "user", "content": "What is the meaning of life?"},
            )

            # Give the workflow time to process and hit the gated activity
            await asyncio.sleep(0.1)

            # Assert in-flight: thinking state
            status = await handle.query(CopilotSessionWorkflow.get_status)
            assert status == "thinking", f"Expected thinking, got {status}"

            # Assert history has user message (not yet the assistant)
            history = await handle.query(CopilotSessionWorkflow.get_history)
            assert len(history) == 1, f"Expected 1 item in history, got {len(history)}"
            assert history[0]["role"] == "user"
            assert history[0]["content"] == "What is the meaning of life?"

            # Allow the activity to proceed
            _mock_activity_event.set()

            # Poll for history to include assistant response
            max_attempts = 50
            for attempt in range(max_attempts):
                history = await handle.query(CopilotSessionWorkflow.get_history)
                if len(history) == 2:
                    break
                await asyncio.sleep(0.1)

            # Assert history has both user and assistant
            assert len(history) == 2, f"Expected 2 items, got {len(history)}"
            assert history[0]["role"] == "user"
            assert history[0]["content"] == "What is the meaning of life?"
            assert history[1]["role"] == "assistant"
            assert history[1]["content"] == "The answer is 42."

            # Assert final state: idle
            status = await handle.query(CopilotSessionWorkflow.get_status)
            assert status == "idle", f"Expected idle after processing, got {status}"

        finally:
            # Clean up
            _mock_activity_event = None
            await handle.terminate()


async def test_copilot_session_tool_use(pydantic_client: Client):
    """CopilotSessionWorkflow tool-use E2E test.

    Tests that tool-use (ToolCall parsing, dispatch, and second LLM call) works:
    - First generate_chat_response call returns tool_call format
    - Workflow parses as ToolCall and dispatches the named tool (get_skeleton)
    - Tool result is appended to history as a tool message with role="tool"
    - Second generate_chat_response call is made with augmented history
    - Final assistant message comes from the second call
    - Workflow returns to idle state

    This test will FAIL (red) against C3 code because:
    - Current code appends raw "TOOL: ..." string as assistant content
    - Never dispatches the tool or makes a second call
    - No tool message in history → AssertionError
    """
    global _mock_activity_event, _tool_use_test_call_count
    _tool_use_test_call_count = 0  # Reset for this test
    task_queue = f"test-copilot-tool-{uuid.uuid4().hex[:8]}"

    # Decorate the stateful mocks for this test's Worker
    chat_activity = activity.defn(name="generate_chat_response")(
        mock_chat_for_tool_use
    )
    skeleton_activity = activity.defn(name="get_skeleton")(mock_get_skeleton_activity)

    async with Worker(
        pydantic_client,
        task_queue=task_queue,
        workflows=[CopilotSessionWorkflow],
        activities=[chat_activity, skeleton_activity],
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        # Start workflow
        handle = await pydantic_client.start_workflow(
            CopilotSessionWorkflow.run,
            {"vault_path": "/dummy/vault", "session_id": "test-tool-use-1"},
            id=f"copilot-tool-test-{uuid.uuid4().hex[:8]}",
            task_queue=task_queue,
        )

        try:
            # Assert initial state: idle
            status = await handle.query(CopilotSessionWorkflow.get_status)
            assert status == "idle", f"Expected initial idle, got {status}"

            # Assert initial history is empty
            history = await handle.query(CopilotSessionWorkflow.get_history)
            assert (
                len(history) == 0
            ), f"Expected empty initial history, got {len(history)} items"

            # Gate the mock activities using threading.Event
            _mock_activity_event = threading.Event()

            # Signal a user message that will trigger tool-use
            await handle.signal(
                CopilotSessionWorkflow.receive_message,
                {"role": "user", "content": "What is in my vault?"},
            )

            # Give the workflow time to process and hit the gated activity
            await asyncio.sleep(0.1)

            # Assert in-flight: thinking state
            status = await handle.query(CopilotSessionWorkflow.get_status)
            assert status == "thinking", f"Expected thinking, got {status}"

            # Assert history has user message (not yet the tool/assistant)
            history = await handle.query(CopilotSessionWorkflow.get_history)
            assert (
                len(history) == 1
            ), f"Expected 1 item in history, got {len(history)}"
            assert history[0]["role"] == "user"
            assert history[0]["content"] == "What is in my vault?"

            # Allow the activities to proceed
            _mock_activity_event.set()

            # Poll for history to include tool message and second assistant response
            # Expected: user + tool + assistant (3 items minimum)
            max_attempts = 50
            for attempt in range(max_attempts):
                history = await handle.query(CopilotSessionWorkflow.get_history)
                if len(history) >= 3:
                    break
                await asyncio.sleep(0.1)

            history = await handle.query(CopilotSessionWorkflow.get_history)

            # === KEY ASSERTIONS THAT FAIL WITH CURRENT CODE ===
            # These will fail because C3 code doesn't handle ToolCall

            # 1. User message should be first
            assert (
                history[0]["role"] == "user"
            ), f"First message should be user, got {history[0].get('role')}"
            assert history[0]["content"] == "What is in my vault?"

            # 2. CRITICAL: Tool message must be present
            # Current code appends raw "TOOL: get_skeleton\nARGS: {}" as assistant,
            # so there will be NO tool message → AssertionError
            tool_messages = [
                m for m in history if m.get("role") == "tool"
            ]
            assert (
                len(tool_messages) > 0
            ), "No tool message in history - tool dispatch failed"
            tool_msg = tool_messages[0]
            assert tool_msg.get("tool_name") == "get_skeleton"
            assert len(tool_msg.get("content", "")) > 0
            assert "vault_structure" in tool_msg.get("content", "")

            # 3. Final assistant message should be from second call
            # Current code has the raw tool string, so this will fail
            assert (
                history[-1]["role"] == "assistant"
            ), f"Last message should be assistant, got {history[-1].get('role')}"
            assert (
                history[-1]["content"] == "Skeleton analysis complete."
            ), f"Final assistant content should be from second call, got {history[-1].get('content')}"

            # 4. Assert final state: idle
            status = await handle.query(CopilotSessionWorkflow.get_status)
            assert status == "idle", f"Expected final idle, got {status}"

        finally:
            # Clean up
            _mock_activity_event = None
            _tool_use_test_call_count = 0
            await handle.terminate()
