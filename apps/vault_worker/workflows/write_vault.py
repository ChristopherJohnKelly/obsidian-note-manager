"""WriteVaultWorkflow — serialised vault mutation handler.

Executes on vault-mutation-queue with max_concurrent_workflow_tasks=1,
max_concurrent_activities=1, guaranteeing sequential execution of all vault writes.

Workflow steps:
1. git_pull (always, unless operations list is empty)
2. For each operation: save_note or delete_note
3. git_commit + git_push (if there were any operations)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from apps.vault_worker.activities.vault_io import save_note, delete_note
    from apps.vault_worker.activities.git_ops import git_pull, git_commit, git_push
    from packages.shared.models import VaultNote


@dataclass
class WriteOperation:
    op: Literal["save", "delete"]
    path: str
    note: VaultNote | None = None  # required when op == "save"


@dataclass
class WriteVaultInput:
    vault_path: str
    operations: list[WriteOperation]
    commit_message: str


@workflow.defn
class WriteVaultWorkflow:
    @workflow.run
    async def run(self, input: WriteVaultInput) -> str:
        """Execute a series of save/delete operations atomically.

        Returns the commit SHA (empty string if no commit was made).
        """
        if not input.operations:
            return ""

        await workflow.execute_activity(
            git_pull,
            args=[input.vault_path],
            schedule_to_close_timeout=timedelta(minutes=5),
        )

        for op in input.operations:
            if op.op == "save":
                if op.note is None:
                    raise ValueError("save operation requires a note")
                await workflow.execute_activity(
                    save_note,
                    args=[input.vault_path, op.path, op.note],
                    schedule_to_close_timeout=timedelta(minutes=1),
                )
            elif op.op == "delete":
                await workflow.execute_activity(
                    delete_note,
                    args=[input.vault_path, op.path],
                    schedule_to_close_timeout=timedelta(minutes=1),
                )
            else:
                raise ValueError(f"Unknown operation: {op.op}")

        commit_sha = await workflow.execute_activity(
            git_commit,
            args=[input.vault_path, input.commit_message],
            schedule_to_close_timeout=timedelta(minutes=1),
        )

        await workflow.execute_activity(
            git_push,
            args=[input.vault_path],
            schedule_to_close_timeout=timedelta(minutes=5),
        )

        return commit_sha
