"""Temporal worker registration for vault-worker.

Registers two workers on separate task queues:
- vault-default: unlimited concurrency, all parent workflows and read-only activities
- vault-mutation-queue: max concurrency 1, only WriteVaultWorkflow and write activities
"""

from concurrent.futures import ThreadPoolExecutor

from temporalio.worker import Worker

from packages.shared.workflow_names import QUEUE_DEFAULT, QUEUE_MUTATION

from apps.vault_worker.activities.vault_io import (
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

from apps.vault_worker.workflows.write_vault import WriteVaultWorkflow


def create_workers(client):
    """Return a list of Workers to run in the same process."""
    default_worker = Worker(
        client,
        task_queue=QUEUE_DEFAULT,
        workflows=[],
        activities=[
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
