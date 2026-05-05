"""E2E test for CopilotSessionWorkflow: single-turn direct response."""

from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import pytest_asyncio
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from apps.vault_worker.activities.llm import configure_provider, generate_chat_response
from apps.vault_worker.workflows.copilot_session import (
    CopilotSessionInput,
    CopilotSessionWorkflow,
)
from packages.shared.workflow_names import (
    QUEUE_DEFAULT,
    QRY_GET_HISTORY,
    QRY_GET_STATUS,
    SIG_CANCEL_SESSION,
    SIG_RECEIVE_MESSAGE,
)
from tests.mocks.fake_llm import FakeLLMProvider


@pytest_asyncio.fixture
async def pydantic_client(temporal_client: Client) -> Client:
    """Temporal client with pydantic data converter for workflow I/O serialization."""
    client = await Client.connect(
        temporal_client.address,
        data_converter=pydantic_data_converter,
    )
    yield client
    await client.close()


@pytest.mark.asyncio
async def test_single_turn_direct_response(
    pydantic_client: Client, dummy_vault_path: str
) -> None:
    """E2E: receive_message signal → direct LLM response → get_history has 2 msgs, get_status idle."""
    # 1. Create fake provider and queue response
    fake = FakeLLMProvider()
    fake.queue_response("Hello, this is a direct response.")

    # 2. Configure provider with try/finally
    configure_provider(fake)
    try:
        # 3. Start worker
        async with Worker(
            pydantic_client,
            task_queue=QUEUE_DEFAULT,
            workflows=[CopilotSessionWorkflow],
            activities=[generate_chat_response],
            activity_executor=ThreadPoolExecutor(max_workers=2),
        ):
            # 4. Start workflow
            handle = await pydantic_client.start_workflow(
                CopilotSessionWorkflow.run,
                CopilotSessionInput(
                    vault_path=str(dummy_vault_path),
                    session_id=f"sess-{uuid.uuid4().hex[:6]}",
                ),
                id=f"copilot-single-turn-{uuid.uuid4().hex[:6]}",
                task_queue=QUEUE_DEFAULT,
            )

            # 5. Inner try/finally for signal
            try:
                # Send signal
                await handle.signal(
                    SIG_RECEIVE_MESSAGE,
                    {"role": "user", "content": "hi"},
                )

                # 6. Poll for status
                for _ in range(50):
                    status = await handle.query(QRY_GET_STATUS)
                    history = await handle.query(QRY_GET_HISTORY)

                    if status == "idle" and len(history) >= 2:
                        break

                    await asyncio.sleep(0.1)

                # 7. Assert history
                history = await handle.query(QRY_GET_HISTORY)
                assert len(history) == 2
                assert history[0]["role"] == "user"
                assert history[0]["content"] == "hi"
                assert history[1]["role"] == "assistant"
                assert history[1]["content"] == "Hello, this is a direct response."

                # 8. Cancel and verify completion
                await handle.signal(SIG_CANCEL_SESSION)
                await handle.result()
                assert await handle.query(QRY_GET_STATUS) == "complete"
            finally:
                # 9. Inner finally: terminate
                try:
                    await handle.terminate()
                except Exception:
                    pass
    finally:
        # 10. Outer finally: unconfigure provider
        configure_provider(None)
