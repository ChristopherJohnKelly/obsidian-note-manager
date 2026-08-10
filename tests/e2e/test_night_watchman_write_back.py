"""E2E tests for NightWatchmanWorkflow write-back behavior (S18 AC3: parse-and-preserve).

Verifies that step 5 of NightWatchmanWorkflow parses LLM output via parse_fix
and writes VaultNote(frontmatter=original_note.frontmatter, body=parsed_body)
rather than storing the raw %%FILE%%...%%END%% string verbatim.

Expected RED before implementation:
- ModuleNotFoundError on import of apps.vault_worker.core.fix_parser, OR
- AssertionError because body still contains %%FILE%%/%%END%% markers and
  frontmatter is the empty Frontmatter() default.
"""

from __future__ import annotations

import asyncio
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import frontmatter as fm
import pytest
import pytest_asyncio
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

# RED: ModuleNotFoundError if fix_parser.py does not yet exist.
from apps.vault_worker.core.fix_parser import parse_fix  # noqa: F401

from apps.vault_worker.activities.vault_io import (
    get_code_registry,
    get_skeleton,
    list_notes_in,
    read_note,
    read_raw,
    save_note,
    scan_vault,
    validate_note,
)
from apps.vault_worker.activities.vault_manager_client import (
    configure_client,
    ensure_vault_synced,
)
from apps.vault_worker.activities.llm import configure_provider, generate_fix
from apps.vault_worker.activities.github_ops import configure_github_client, create_github_pr
from apps.vault_worker.workflows.night_watchman import (
    NightWatchmanInput,
    NightWatchmanWorkflow,
)
from apps.vault_worker.workflows.read_vault import ReadVaultInput, ReadVaultWorkflow
from apps.vault_worker.workflows.write_vault import WriteVaultWorkflow
from packages.shared.models import Frontmatter, VaultNote
from packages.shared.workflow_names import (
    QUEUE_DEFAULT,
    QUEUE_MUTATION,
    UPD_ENSURE_SYNCED,
    VAULT_MANAGER_ID,
)
from tests.mocks.fake_github import FakeGitHubClient
from tests.mocks.fake_llm import FakeLLMProvider


# ---------------------------------------------------------------------------
# Module-level capture list — populated by capturing_save_note below
# ---------------------------------------------------------------------------

_writeback_captured: list[tuple[str, VaultNote]] = []


# ---------------------------------------------------------------------------
# Inline stubs (same pattern as test_night_watchman_workflow.py)
# ---------------------------------------------------------------------------


@workflow.defn
class VaultManagerStub:
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
def capturing_save_note(vault_root: str, path: str, note: VaultNote) -> None:
    """Capture each save_note call for later assertion."""
    _writeback_captured.append((path, note))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def pydantic_client(temporal_client: Client) -> Client:
    """Client with pydantic_data_converter, same as test_night_watchman_workflow.py."""
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
# AC3 acceptance test
# ---------------------------------------------------------------------------


async def test_parse_and_preserve_frontmatter(pydantic_client, dummy_vault_path):
    """AC3: step 5 writes parsed body + original frontmatter, not raw LLM markers.

    RED assertions (before implementation):
    - note.body contains %%FILE%%/%%END%% markers → AssertionError, or
    - note.frontmatter == Frontmatter() (empty default) → AssertionError.

    GREEN assertions (after implementation):
    - len(captured) >= 1
    - "%%FILE%%" not in note.body for every captured note
    - "%%END%%" not in note.body for every captured note
    - note.frontmatter preserves the original vault note's title (not empty)
    """
    global _writeback_captured
    _writeback_captured = []

    # Pre-scan vault frontmatter so we can verify preservation after the run.
    originals: dict[str, dict] = {}
    vault = Path(dummy_vault_path)
    for folder in ["20. Projects/TEST-P01", "30. Areas/1. Test Area"]:
        folder_path = vault / folder
        if not folder_path.exists():
            continue
        for md_file in sorted(folder_path.glob("*.md")):
            post = fm.load(str(md_file))
            rel = str(md_file.relative_to(vault))
            originals[rel] = dict(post.metadata)

    fake_llm = FakeLLMProvider()
    configure_provider(fake_llm)
    fake_github = FakeGitHubClient()
    configure_github_client(lambda token: fake_github)

    try:
        async with Worker(
            pydantic_client,
            task_queue=QUEUE_DEFAULT,
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
                task_queue=QUEUE_MUTATION,
                workflows=[WriteVaultWorkflow],
                activities=[
                    capturing_save_note,
                    noop_git_pull,
                    noop_git_commit,
                    noop_git_push,
                ],
                activity_executor=ThreadPoolExecutor(max_workers=2),
            ):
                stub_handle = await pydantic_client.start_workflow(
                    VaultManagerStub.run,
                    id=VAULT_MANAGER_ID,
                    task_queue=QUEUE_DEFAULT,
                    id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
                )
                try:
                    await pydantic_client.execute_workflow(
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
                        id=f"nw-writeback-{uuid.uuid4().hex[:4]}",
                        task_queue=QUEUE_DEFAULT,
                    )
                finally:
                    await stub_handle.cancel()
    finally:
        configure_provider(None)
        configure_github_client(None)

    captured = list(_writeback_captured)
    assert len(captured) >= 1, (
        f"Expected at least one save_note call, got {len(captured)}"
    )

    for path, note in captured:
        assert "%%FILE%%" not in note.body, (
            f"Raw %%FILE%% marker in body for {path!r} — LLM output was not parsed"
        )
        assert "%%END%%" not in note.body, (
            f"Raw %%END%% marker in body for {path!r} — LLM output was not parsed"
        )

        # Verify frontmatter is preserved from the original vault note.
        expected = originals.get(path)
        if expected and expected.get("title"):
            assert note.frontmatter.title == expected["title"], (
                f"Frontmatter title not preserved for {path!r}: "
                f"expected {expected['title']!r}, got {note.frontmatter.title!r}"
            )
        else:
            # No pre-scanned original: verify it is not the empty Frontmatter() default.
            assert note.frontmatter != Frontmatter(), (
                f"Empty default frontmatter written for {path!r} — "
                "original frontmatter was not preserved"
            )


# ---------------------------------------------------------------------------
# AC4 skip-path characterization test
# ---------------------------------------------------------------------------


class MalformedLLMProvider(FakeLLMProvider):
    """LLM provider returning a configurable bad output.

    Both variants must resolve to parse_fix -> None -> zero WriteOperations:
    markerless text (no %%FILE%% block), and a marker-wrapped block whose
    frontmatter YAML is malformed — the case that once raised
    yaml.ParserError out of @workflow.run into an infinite retry loop.
    """

    def __init__(self, bad_output: str) -> None:
        super().__init__()
        self._bad_output = bad_output

    def generate_fix(self, *args, **kwargs) -> str:
        return self._bad_output


MALFORMED_OUTPUTS = [
    "the LLM had a bad day",
    "%%FILE%%\npath: notes/x.md\n---\nkey: [unclosed\n---\nbody text\n%%END%%",
]


@pytest.mark.parametrize("bad_output", MALFORMED_OUTPUTS)
async def test_malformed_llm_skips_all(pydantic_client, tmp_path, bad_output):
    """AC4: markerless LLM output → parse_fix returns None → zero save_note, vault unchanged.

    Characterization test: C3 already implements this skip path.
    - fix_parser.py:26 `return body or None` makes parse_fix return strict None for
      markerless input.
    - night_watchman.py:94-96 `if body is None: continue` produces zero WriteOperations.
    - write_vault.py:48-49 `if not input.operations: return ""` exits without save_note/git.
    This test pins that contract so a future regression (e.g. returning "" instead of None)
    cannot silently reintroduce data loss.
    """
    global _writeback_captured
    _writeback_captured = []

    # Copy dummy_vault into tmp_path and snapshot .md bytes pre-run.
    fixture_vault = Path(__file__).parent.parent / "fixtures" / "dummy_vault"
    vault_root = tmp_path / "vault"
    shutil.copytree(str(fixture_vault), str(vault_root))

    pre = {
        p.relative_to(vault_root): p.read_bytes()
        for p in vault_root.rglob("*.md")
    }

    malformed_llm = MalformedLLMProvider(bad_output)
    configure_provider(malformed_llm)
    fake_github = FakeGitHubClient()
    configure_github_client(lambda token: fake_github)

    try:
        async with Worker(
            pydantic_client,
            task_queue=QUEUE_DEFAULT,
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
                task_queue=QUEUE_MUTATION,
                workflows=[WriteVaultWorkflow],
                activities=[
                    save_note,
                    noop_git_pull,
                    noop_git_commit,
                    noop_git_push,
                ],
                activity_executor=ThreadPoolExecutor(max_workers=2),
            ):
                stub_handle = await pydantic_client.start_workflow(
                    VaultManagerStub.run,
                    id=VAULT_MANAGER_ID,
                    task_queue=QUEUE_DEFAULT,
                    id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
                )
                try:
                    await pydantic_client.execute_workflow(
                        NightWatchmanWorkflow.run,
                        NightWatchmanInput(
                            vault_path=str(vault_root),
                            context_code="TEST-P01",
                            repo_owner="test-owner",
                            repo_name="test-repo",
                            github_token="fake-token",
                            pr_branch="audit/night-watchman",
                            base_branch="main",
                        ),
                        id=f"nw-skip-{uuid.uuid4().hex[:4]}",
                        task_queue=QUEUE_DEFAULT,
                    )
                finally:
                    await stub_handle.cancel()
    finally:
        configure_provider(None)
        configure_github_client(None)


    post = {
        p.relative_to(vault_root): p.read_bytes()
        for p in vault_root.rglob("*.md")
    }
    assert post == pre, (
        "Vault .md files mutated despite malformed LLM output — "
        "WriteVaultWorkflow should have returned '' without touching disk.\n"
        f"Changed files: {[str(k) for k in post if post[k] != pre.get(k)]}"
    )
