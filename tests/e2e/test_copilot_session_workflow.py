"""E2E tests for Copilot session workflow Activities.

Tests the generate_chat_response Activity and FakeLLMProvider chat/react methods
used in the Temporal Copilot session workflow.
"""

import pytest

from apps.vault_worker.activities.llm import (
    configure_provider,
    generate_chat_response,
)
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
