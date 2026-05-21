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
