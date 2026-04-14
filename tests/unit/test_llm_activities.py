"""Unit tests for LLM Generation Activities (OBSE-P5-S06).

TDD: Tests written before implementation. All tests fail until Activities implemented.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from temporalio import activity, workflow
from temporalio.worker import Worker

from packages.shared.models import Frontmatter, VaultContext, VaultNote
from tests.mocks.fake_llm import FakeLLMProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context() -> VaultContext:
    root_note = VaultNote(
        path=Path("20. Projects/TEST-P01/TEST-P01 - Project Root.md"),
        frontmatter=Frontmatter(
            code="TEST-P01",
            type="project",
            aliases=["Test P01"],
            tags=["type/project"],
        ),
        body="Project root.",
    )
    return VaultContext(
        context_code="TEST-P01",
        root_note=root_note,
        related_notes=[],
        skeleton="- [[Test P01]] (20. Projects/TEST-P01/TEST-P01 - Project Root.md)",
        code_registry="| TEST-P01 | Test Project | project | 20. Projects/TEST-P01 |",
    )


def _make_rule2_note() -> VaultNote:
    return VaultNote(
        path=Path("20. Projects/TEST-P01/wrong-prefix-note.md"),
        frontmatter=Frontmatter(
            type="content",
            aliases=["Wrong"],
            tags=["type/content"],
        ),
        body="Note with wrong prefix — Rule 2 violation.",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def inject_fake_llm():
    """Configure FakeLLMProvider before each test; reset after."""
    from apps.vault_worker.activities.llm import configure_provider
    configure_provider(FakeLLMProvider())
    yield
    configure_provider(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AC1: generate_proposal returns %%FILE%% and %%END%%
# ---------------------------------------------------------------------------


def test_generate_proposal_returns_file_markers():
    """AC: generate_proposal with FakeLLMProvider returns a string with %%FILE%% and %%END%%."""
    from apps.vault_worker.activities.llm import generate_proposal
    ctx = _make_context()
    result = generate_proposal(ctx, "# Raw inbox note\nContent here.")
    assert "%%FILE%%" in result
    assert "%%END%%" in result


# ---------------------------------------------------------------------------
# AC2: generate_fix returns valid fix response
# ---------------------------------------------------------------------------


def test_generate_fix_returns_file_markers():
    """AC: generate_fix with Rule 2 violation note and FakeLLMProvider returns %%FILE%% and %%END%%."""
    from apps.vault_worker.activities.llm import generate_fix
    note = _make_rule2_note()
    ctx = _make_context()
    result = generate_fix(note, ["Missing Project Code: TEST-P01"], ctx)
    assert "%%FILE%%" in result
    assert "%%END%%" in result


# ---------------------------------------------------------------------------
# AC3: LLM_RETRY_POLICY defined correctly
# ---------------------------------------------------------------------------


def test_llm_retry_policy_attributes():
    """AC: LLM_RETRY_POLICY has max 3 attempts, 1s initial interval, 2.0 backoff, ValueError non-retryable."""
    from apps.vault_worker.activities.llm import LLM_RETRY_POLICY
    assert LLM_RETRY_POLICY.maximum_attempts == 3
    assert LLM_RETRY_POLICY.initial_interval == timedelta(seconds=1)
    assert LLM_RETRY_POLICY.backoff_coefficient == 2.0
    assert "ValueError" in (LLM_RETRY_POLICY.non_retryable_error_types or [])


# ---------------------------------------------------------------------------
# AC4: Retry test using Temporal test environment
# ---------------------------------------------------------------------------

_call_count = 0


@activity.defn
def _flaky_generate() -> str:
    """Activity that fails on first call and succeeds on second — simulates transient failure."""
    global _call_count
    _call_count += 1
    if _call_count < 2:
        raise RuntimeError("transient failure")
    return "%%FILE%%\npath: test.md\n---\n---\n%%END%%"


@workflow.defn
class _RetryTestWorkflow:
    @workflow.run
    async def run(self) -> str:
        from apps.vault_worker.activities.llm import LLM_RETRY_POLICY
        return await workflow.execute_activity(
            _flaky_generate,
            schedule_to_close_timeout=timedelta(seconds=10),
            retry_policy=LLM_RETRY_POLICY,
        )


async def test_generate_retries_on_transient_failure(temporal_client):
    """AC: Retry policy fires on transient RuntimeError; activity succeeds on second attempt."""
    global _call_count
    _call_count = 0
    async with Worker(
        temporal_client,
        task_queue="llm-retry-test-q",
        workflows=[_RetryTestWorkflow],
        activities=[_flaky_generate],
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        result = await temporal_client.execute_workflow(
            _RetryTestWorkflow.run,
            id="llm-retry-test",
            task_queue="llm-retry-test-q",
        )
    assert _call_count == 2
    assert "%%FILE%%" in result


# ---------------------------------------------------------------------------
# AC5: response_parser extracts files from %%FILE%%...%%END%% format
# ---------------------------------------------------------------------------


def test_parse_llm_response_fake_proposal():
    """AC: parse_llm_response extracts path and content from FakeLLMProvider FAKE_PROPOSAL."""
    from apps.vault_worker.core.response_parser import parse_llm_response
    raw = FakeLLMProvider.FAKE_PROPOSAL
    files = parse_llm_response(raw)
    assert len(files) == 1
    assert files[0]["path"] == "30. Areas/1. Test Area/AREA - Filed Note.md"
    assert "%%FILE%%" not in files[0]["content"]
    assert "%%END%%" not in files[0]["content"]
    assert "Filed Note" in files[0]["content"]


def test_parse_llm_response_handcrafted_fixture():
    """AC: parse_llm_response handles a hand-crafted two-block %%FILE%% fixture."""
    from apps.vault_worker.core.response_parser import parse_llm_response
    raw = (
        "%%FILE%%\n"
        "path: 20. Projects/P01/P01 - Note.md\n"
        "---\n"
        "type: content\n"
        "---\n"
        "# Note Body\n"
        "Content here.\n"
        "%%END%%\n"
        "%%FILE%%\n"
        "path: 20. Projects/P01/P01 - Second.md\n"
        "---\n"
        "type: content\n"
        "---\n"
        "Second body.\n"
        "%%END%%"
    )
    files = parse_llm_response(raw)
    assert len(files) == 2
    assert files[0]["path"] == "20. Projects/P01/P01 - Note.md"
    assert files[1]["path"] == "20. Projects/P01/P01 - Second.md"
    assert "Content here." in files[0]["content"]
    assert "Second body." in files[1]["content"]
