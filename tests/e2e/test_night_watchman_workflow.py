"""E2E tests for NightWatchmanWorkflow.

NightWatchmanWorkflow orchestrates the full audit loop: sync → scan → sort →
slice[:10] → generate_fix loop → WriteVault → create_github_pr.
"""

from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest_asyncio
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from apps.vault_worker.activities.vault_io import (
    get_code_registry,
    get_skeleton,
    list_notes_in,
    read_note,
    read_raw,
    scan_vault,
    validate_note,
)
from apps.vault_worker.activities.vault_manager_client import (
    configure_client,
    ensure_vault_synced,
)
from apps.vault_worker.activities.llm import (
    generate_fix,
)
from apps.vault_worker.activities.github_ops import (
    configure_github_client,
    create_github_pr,
)
from apps.vault_worker.workflows.night_watchman import (
    NightWatchmanInput,
    NightWatchmanWorkflow,
)
from apps.vault_worker.workflows.read_vault import ReadVaultInput, ReadVaultWorkflow
from apps.vault_worker.workflows.write_vault import (
    WriteVaultWorkflow,
)
from packages.shared.models import ValidationResult, VaultNote
from packages.shared.workflow_names import (
    QUEUE_DEFAULT,
    QUEUE_MUTATION,
    UPD_ENSURE_SYNCED,
    VAULT_MANAGER_ID,
)
from tests.mocks.fake_github import FakeGitHubClient
from tests.mocks.fake_llm import FakeLLMProvider


# ---------------------------------------------------------------------------
# Inline stubs — minimal stand-ins for VaultManagerWorkflow (full impl in S09)
# ---------------------------------------------------------------------------


@workflow.defn
class VaultManagerStub:
    """Accepts ensure_synced Update; returns immediately (fresh vault)."""

    def __init__(self) -> None:
        self._call_count: int = 0

    @workflow.update(name=UPD_ENSURE_SYNCED)
    async def on_ensure_synced(self) -> None:
        self._call_count += 1

    @workflow.query
    def call_count(self) -> int:
        return self._call_count

    @workflow.run
    async def run(self) -> None:
        await asyncio.sleep(3600)


# ---------------------------------------------------------------------------
# Mock activities for external dependencies
# ---------------------------------------------------------------------------


@activity.defn(name="git_pull")
def noop_git_pull(vault_path: str) -> None:
    pass


@activity.defn(name="git_commit")
def noop_git_commit(vault_path: str, message: str) -> str:
    return "fake-sha-0123456789abcdef0123456789abcdef01234567"


@activity.defn(name="git_push")
def noop_git_push(vault_path: str) -> None:
    pass


@activity.defn(name="save_note")
def noop_save_note(vault_root: str, path: str, note) -> None:
    pass


# Module-level mock activities for C3 characterization test
# (defined at module scope to avoid type hint resolution issues with from __future__ import annotations)

_c3_synthetic_results = []


@activity.defn(name="scan_vault")
async def mock_scan_vault_c3(vault_root: str) -> list:
    return _c3_synthetic_results


@activity.defn(name="read_note")
async def mock_read_note_c3(vault_path: str, note_path: str):
    return VaultNote(
        path=note_path,
        content=f"# Test Note\n\nPath: {note_path}",
        frontmatter={},
        links=[],
        backlinks=[],
        area_note_path=None,
    )


@activity.defn(name="get_code_registry")
def mock_get_code_registry(vault_root: str, context_code: str) -> dict:
    return {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def pydantic_client(temporal_client: Client) -> Client:
    """Client with pydantic_data_converter."""
    client = Client(
        service_client=temporal_client.service_client,
        namespace=temporal_client.namespace,
        data_converter=pydantic_data_converter,
    )
    configure_client(client)
    try:
        yield client
    finally:
        configure_client(None)


# ---------------------------------------------------------------------------
# Acceptance tests
# ---------------------------------------------------------------------------


async def test_happy_path_end_to_end(pydantic_client, dummy_vault_path):
    """NightWatchmanWorkflow happy-path E2E: sync→scan→sort→slice[:10]→
    generate_fix loop→WriteVault→create_github_pr.

    - Configures FakeLLMProvider and FakeGitHubClient
    - Runs two Workers: one on QUEUE_DEFAULT (read + analysis), one on QUEUE_MUTATION (write)
    - Starts VaultManagerStub to handle ensure_synced Update
    - Executes NightWatchmanWorkflow
    - Asserts result has 0 < proposals_generated <= 10
    - Asserts pr_url starts with "https://fake.invalid/"
    - Asserts fake client's prs_created has length 1 with correct head/base
    """
    from apps.vault_worker.activities.llm import configure_provider

    # Configure LLM provider
    fake_llm = FakeLLMProvider()
    configure_provider(fake_llm)

    # Configure GitHub client
    fake_github = FakeGitHubClient()
    configure_github_client(lambda token: fake_github)

    default_queue = QUEUE_DEFAULT
    mutation_queue = QUEUE_MUTATION

    try:
        # Start both workers
        async with Worker(
            pydantic_client,
            task_queue=default_queue,
            workflows=[VaultManagerStub, ReadVaultWorkflow, NightWatchmanWorkflow],
            activities=[
                get_code_registry,
                get_skeleton,
                read_note,
                list_notes_in,
                read_raw,
                scan_vault,
                validate_note,
                generate_fix,
                create_github_pr,
                ensure_vault_synced,
            ],
            activity_executor=ThreadPoolExecutor(max_workers=4),
        ):
            async with Worker(
                pydantic_client,
                task_queue=mutation_queue,
                workflows=[WriteVaultWorkflow],
                activities=[
                    noop_save_note,
                    noop_git_pull,
                    noop_git_commit,
                    noop_git_push,
                ],
                activity_executor=ThreadPoolExecutor(max_workers=2),
            ):
                # Start VaultManagerStub
                stub_handle = await pydantic_client.start_workflow(
                    VaultManagerStub.run,
                    id=VAULT_MANAGER_ID,
                    task_queue=default_queue,
                    id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
                )

                try:
                    # Execute NightWatchmanWorkflow
                    result = await pydantic_client.execute_workflow(
                        NightWatchmanWorkflow.run,
                        NightWatchmanInput(
                            vault_path=str(dummy_vault_path),
                            context_code="TEST-P01",
                            repo_owner="test-owner",
                            repo_name="test-repo",
                            github_token="fake-token",
                            pr_branch="audit/night-watchman",
                            base_branch="main",
                        ),
                        id=f"night-watchman-happy-{uuid.uuid4().hex[:4]}",
                        task_queue=default_queue,
                    )

                    # Assertions
                    assert isinstance(result, dict)
                    assert "proposals_generated" in result
                    assert "pr_url" in result

                    proposals = result["proposals_generated"]
                    assert 0 < proposals <= 10, f"proposals_generated={proposals}, expected 0 < x <= 10"

                    pr_url = result["pr_url"]
                    assert pr_url.startswith("https://fake.invalid/"), f"pr_url={pr_url}"

                    # Check GitHub client was called correctly
                    assert len(fake_github.prs_created) == 1
                    pr_call = fake_github.prs_created[0]
                    assert pr_call["head"] == "audit/night-watchman"
                    assert pr_call["base"] == "main"

                finally:
                    await stub_handle.cancel()

    finally:
        configure_provider(None)
        configure_github_client(None)


async def test_top_ten_cap_with_synthetic_results(pydantic_client, dummy_vault_path):
    """Characterization: prove the top-10 slice doesn't regress.

    - Mock scan_vault to return 12 synthetic ValidationResults with scores 1..12
    - Use CountingFakeLLMProvider to track generate_fix calls
    - Assert result["proposals_generated"] == 10
    - Assert len(counting_provider.calls) == 10
    - Assert top 10 highest-scoring paths were passed to generate_fix
    """
    from apps.vault_worker.activities.llm import configure_provider

    # Create CountingFakeLLMProvider that wraps FakeLLMProvider
    class CountingFakeLLMProvider(FakeLLMProvider):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[str] = []

        def generate_fix(self, instructions: str, body: str, context: str, skeleton: str) -> str:
            # Extract the note path from the instructions (stored as "The note is at: {path}")
            if "The note is at:" in instructions:
                path = instructions.split("The note is at: ")[-1].strip()
                self.calls.append(path)
            return super().generate_fix(instructions=instructions, body=body, context=context, skeleton=skeleton)

    # Set up synthetic results for the module-level mock activity
    global _c3_synthetic_results
    _c3_synthetic_results = [
        ValidationResult(
            path=f"20. Projects/TEST-P01/note-{i:02d}.md",
            score=float(i),
            issues=[],
        )
        for i in range(1, 13)
    ]

    # Configure mocks
    counting_provider = CountingFakeLLMProvider()
    configure_provider(counting_provider)

    fake_github = FakeGitHubClient()
    configure_github_client(lambda token: fake_github)

    default_queue = QUEUE_DEFAULT
    mutation_queue = QUEUE_MUTATION

    try:
        # Start workers with mocked scan_vault and read_note
        async with Worker(
            pydantic_client,
            task_queue=default_queue,
            workflows=[VaultManagerStub, ReadVaultWorkflow, NightWatchmanWorkflow],
            activities=[
                get_code_registry,
                get_skeleton,
                mock_read_note_c3,
                list_notes_in,
                read_raw,
                mock_scan_vault_c3,
                validate_note,
                generate_fix,
                create_github_pr,
                ensure_vault_synced,
            ],
            activity_executor=ThreadPoolExecutor(max_workers=4),
        ):
            async with Worker(
                pydantic_client,
                task_queue=mutation_queue,
                workflows=[WriteVaultWorkflow],
                activities=[
                    noop_save_note,
                    noop_git_pull,
                    noop_git_commit,
                    noop_git_push,
                ],
                activity_executor=ThreadPoolExecutor(max_workers=2),
            ):
                # Start VaultManagerStub
                stub_handle = await pydantic_client.start_workflow(
                    VaultManagerStub.run,
                    id=VAULT_MANAGER_ID,
                    task_queue=default_queue,
                    id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
                )

                try:
                    # Execute workflow with synthetic inputs
                    result = await pydantic_client.execute_workflow(
                        NightWatchmanWorkflow.run,
                        NightWatchmanInput(
                            vault_path=str(dummy_vault_path),
                            context_code="TEST-P01",
                            repo_owner="test-owner",
                            repo_name="test-repo",
                            github_token="fake-token",
                            pr_branch="audit/night-watchman",
                            base_branch="main",
                        ),
                        id=f"night-watchman-top10-{uuid.uuid4().hex[:4]}",
                        task_queue=default_queue,
                    )

                    # Assert exactly 10 proposals generated (top-10 cap)
                    assert result["proposals_generated"] == 10, (
                        f"Expected proposals_generated=10, got {result.get('proposals_generated')}"
                    )

                    # Assert generate_fix called exactly 10 times
                    assert len(counting_provider.calls) == 10, (
                        f"Expected 10 generate_fix calls, got {len(counting_provider.calls)}"
                    )

                    # Assert the correct 10 paths (highest scores: 12,11,10,9,8,7,6,5,4,3)
                    expected_paths = {
                        f"20. Projects/TEST-P01/note-{i:02d}.md"
                        for i in range(3, 13)
                    }
                    actual_paths = set(counting_provider.calls)
                    assert actual_paths == expected_paths, (
                        f"Path mismatch:\n  Expected: {sorted(expected_paths)}\n  Got: {sorted(actual_paths)}"
                    )

                finally:
                    await stub_handle.cancel()

    finally:
        configure_provider(None)
        configure_github_client(None)


async def test_fault_isolation_single_llm_failure(pydantic_client, dummy_vault_path):
    """Characterization: fault isolation — one generate_fix failure yields N-1 proposals, PR still created.

    - Define FailingOnceLLMProvider whose generate_fix raises ValueError("simulated LLM failure")
      when instructions contain a pinned path substring (note-12.md)
    - Run workflow with synthetic results (12 items, top-10 slice)
    - Assert result["proposals_generated"] == 9 (one failure isolated, others succeed)
    - Assert len(fake_github.prs_created) == 1 (PR created despite the failure)
    - Verify workflow catches ActivityError and continues processing remaining items
    """
    from apps.vault_worker.activities.llm import configure_provider

    # Create FailingOnceLLMProvider that fails for a specific path
    class FailingOnceLLMProvider(FakeLLMProvider):
        def __init__(self, failing_path_substring: str = "note-12.md") -> None:
            super().__init__()
            self.failing_path_substring = failing_path_substring

        def generate_fix(self, instructions: str, body: str, context: str, skeleton: str) -> str:
            # Fail if instructions contain the failing path substring
            if self.failing_path_substring in instructions:
                raise ValueError(f"simulated LLM failure for {self.failing_path_substring}")

            return super().generate_fix(instructions=instructions, body=body, context=context, skeleton=skeleton)

    # Set up synthetic results for the module-level mock activity (12 items)
    global _c3_synthetic_results
    _c3_synthetic_results = [
        ValidationResult(
            path=f"20. Projects/TEST-P01/note-{i:02d}.md",
            score=float(i),
            issues=[],
        )
        for i in range(1, 13)
    ]

    # Configure mocks: FailingOnceLLMProvider fails for note-12.md (highest score, in top-10)
    failing_provider = FailingOnceLLMProvider(failing_path_substring="note-12.md")
    configure_provider(failing_provider)

    fake_github = FakeGitHubClient()
    configure_github_client(lambda token: fake_github)

    default_queue = QUEUE_DEFAULT
    mutation_queue = QUEUE_MUTATION

    try:
        # Start workers with mocked scan_vault and read_note
        async with Worker(
            pydantic_client,
            task_queue=default_queue,
            workflows=[VaultManagerStub, ReadVaultWorkflow, NightWatchmanWorkflow],
            activities=[
                get_code_registry,
                get_skeleton,
                mock_read_note_c3,
                list_notes_in,
                read_raw,
                mock_scan_vault_c3,
                validate_note,
                generate_fix,
                create_github_pr,
                ensure_vault_synced,
            ],
            activity_executor=ThreadPoolExecutor(max_workers=4),
        ):
            async with Worker(
                pydantic_client,
                task_queue=mutation_queue,
                workflows=[WriteVaultWorkflow],
                activities=[
                    noop_save_note,
                    noop_git_pull,
                    noop_git_commit,
                    noop_git_push,
                ],
                activity_executor=ThreadPoolExecutor(max_workers=2),
            ):
                # Start VaultManagerStub
                stub_handle = await pydantic_client.start_workflow(
                    VaultManagerStub.run,
                    id=VAULT_MANAGER_ID,
                    task_queue=default_queue,
                    id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
                )

                try:
                    # Execute workflow with synthetic inputs
                    result = await pydantic_client.execute_workflow(
                        NightWatchmanWorkflow.run,
                        NightWatchmanInput(
                            vault_path=str(dummy_vault_path),
                            context_code="TEST-P01",
                            repo_owner="test-owner",
                            repo_name="test-repo",
                            github_token="fake-token",
                            pr_branch="audit/night-watchman",
                            base_branch="main",
                        ),
                        id=f"night-watchman-fault-isolation-{uuid.uuid4().hex[:4]}",
                        task_queue=default_queue,
                    )

                    # Assert result has 9 proposals (one failure isolated)
                    assert result["proposals_generated"] == 9, (
                        f"Expected proposals_generated=9 (one failure), got {result.get('proposals_generated')}"
                    )

                    # Assert PR was still created despite one generate_fix failure
                    assert len(fake_github.prs_created) == 1, (
                        f"Expected 1 PR created, got {len(fake_github.prs_created)}"
                    )
                    pr_call = fake_github.prs_created[0]
                    assert pr_call["head"] == "audit/night-watchman"
                    assert pr_call["base"] == "main"

                finally:
                    await stub_handle.cancel()

    finally:
        configure_provider(None)
        configure_github_client(None)


async def test_get_progress_reports_final_counts(pydantic_client, dummy_vault_path):
    """Query get_progress after workflow completes; assert final counts match proposals.

    - Run workflow to completion using same Dummy Vault setup as C2 happy path
    - Query get_progress after workflow finishes
    - Assert returned dict equals {"files_scanned": N, "proposals_generated": N}
      where N == result["proposals_generated"] from the completed workflow
    """
    from apps.vault_worker.activities.llm import configure_provider

    # Configure LLM provider
    fake_llm = FakeLLMProvider()
    configure_provider(fake_llm)

    # Configure GitHub client
    fake_github = FakeGitHubClient()
    configure_github_client(lambda token: fake_github)

    default_queue = QUEUE_DEFAULT
    mutation_queue = QUEUE_MUTATION

    try:
        # Start both workers with real vault (not mocked)
        async with Worker(
            pydantic_client,
            task_queue=default_queue,
            workflows=[VaultManagerStub, ReadVaultWorkflow, NightWatchmanWorkflow],
            activities=[
                get_code_registry,
                get_skeleton,
                read_note,
                list_notes_in,
                read_raw,
                scan_vault,
                validate_note,
                generate_fix,
                create_github_pr,
                ensure_vault_synced,
            ],
            activity_executor=ThreadPoolExecutor(max_workers=4),
        ):
            async with Worker(
                pydantic_client,
                task_queue=mutation_queue,
                workflows=[WriteVaultWorkflow],
                activities=[
                    noop_save_note,
                    noop_git_pull,
                    noop_git_commit,
                    noop_git_push,
                ],
                activity_executor=ThreadPoolExecutor(max_workers=2),
            ):
                # Start VaultManagerStub
                stub_handle = await pydantic_client.start_workflow(
                    VaultManagerStub.run,
                    id=VAULT_MANAGER_ID,
                    task_queue=default_queue,
                    id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
                )

                try:
                    # Start workflow and wait for completion
                    handle = await pydantic_client.start_workflow(
                        NightWatchmanWorkflow.run,
                        NightWatchmanInput(
                            vault_path=str(dummy_vault_path),
                            context_code="TEST-P01",
                            repo_owner="test-owner",
                            repo_name="test-repo",
                            github_token="fake-token",
                            pr_branch="audit/night-watchman",
                            base_branch="main",
                        ),
                        id=f"night-watchman-progress-{uuid.uuid4().hex[:4]}",
                        task_queue=default_queue,
                    )

                    result = await handle.result()
                    proposals_generated = result["proposals_generated"]

                    # Query get_progress after workflow completes
                    progress = await handle.query("get_progress")

                    # Assert progress dict matches expected values
                    assert progress == {
                        "files_scanned": proposals_generated,
                        "proposals_generated": proposals_generated,
                    }

                finally:
                    await stub_handle.cancel()

    finally:
        configure_provider(None)
        configure_github_client(None)
