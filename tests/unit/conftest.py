"""Unit-test fixtures that shadow session-scoped conftest for legacy src_v2 tests."""

import pytest


def _FakeLLM():
    from src_v2.infrastructure.testing.adapters import FakeLLM
    return FakeLLM


@pytest.fixture
def fake_llm():
    """Legacy src_v2 FakeLLM — echoes prompts for service-layer assertion tests."""
    return _FakeLLM()()
