"""Temporal worker registration for vault-worker.

Registers two workers on separate task queues:
- vault-default: unlimited concurrency, all parent workflows and read-only activities
- vault-mutation-queue: max concurrency 1, only WriteVaultWorkflow and write activities
"""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.worker import Worker

from packages.shared.workflow_names import (
    QUEUE_DEFAULT,
    QUEUE_MUTATION,
    VAULT_MANAGER_ID,
)

from apps.vault_worker.activities.vault_io import (
    check_vault_dir_state,
    read_note,
    save_note,
    delete_note,
    list_notes_in,
    read_raw,
    scan_vault,
    validate_note,
    get_skeleton,
    get_code_registry,
)
from apps.vault_worker.activities.git_ops import (
    git_clone,
    git_pull,
    git_commit,
    git_push,
)
from apps.vault_worker.activities.llm import (
    generate_proposal,
    generate_fix,
)
from apps.vault_worker.activities.github_ops import create_github_pr

from apps.vault_worker.workflows.night_watchman import NightWatchmanWorkflow
from apps.vault_worker.workflows.read_vault import ReadVaultWorkflow
from apps.vault_worker.workflows.vault_manager import (
    VaultManagerInput,
    VaultManagerWorkflow,
)
from apps.vault_worker.workflows.write_vault import WriteVaultWorkflow


def create_workers(client):
    """Return a list of Workers to run in the same process."""
    default_worker = Worker(
        client,
        task_queue=QUEUE_DEFAULT,
        workflows=[VaultManagerWorkflow, NightWatchmanWorkflow, ReadVaultWorkflow],
        activities=[
            check_vault_dir_state,
            read_note,
            list_notes_in,
            read_raw,
            scan_vault,
            validate_note,
            get_skeleton,
            get_code_registry,
            git_clone,
            git_pull,
            git_commit,
            git_push,
            generate_proposal,
            generate_fix,
            create_github_pr,
        ],
        activity_executor=ThreadPoolExecutor(max_workers=2),
    )

    mutation_worker = Worker(
        client,
        task_queue=QUEUE_MUTATION,
        workflows=[WriteVaultWorkflow],
        activities=[save_note, delete_note, git_pull, git_commit, git_push],
        max_concurrent_workflow_tasks=1,
        max_concurrent_activities=1,
        activity_executor=ThreadPoolExecutor(max_workers=2),
    )

    return [default_worker, mutation_worker]


async def start_vault_manager(client: Client, vault_input: VaultManagerInput) -> None:
    """Start VaultManagerWorkflow with the well-known ID and poll until ready.

    Must be called AFTER the default Worker is running so the workflow's
    startup activities can execute. Returns only once ``get_sync_status``
    reports ``status == 'ready'``. Blocks indefinitely if the workflow never
    reaches ready; in production the caller should bound this with a timeout.
    """
    await client.start_workflow(
        VaultManagerWorkflow.run,
        vault_input,
        id=VAULT_MANAGER_ID,
        task_queue=QUEUE_DEFAULT,
        id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
    )
    handle = client.get_workflow_handle(VAULT_MANAGER_ID)
    while True:
        status = await handle.query("get_sync_status")
        if status["status"] == "ready":
            return
        await asyncio.sleep(1)


def vault_input_from_env() -> VaultManagerInput:
    """Build VaultManagerInput from the VAULT_PATH / REPO_URL / GITHUB_PAT env vars."""
    return VaultManagerInput(
        vault_path=os.environ["VAULT_PATH"],
        repo_url=os.environ["REPO_URL"],
        pat=os.environ["GITHUB_PAT"],
    )
