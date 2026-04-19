"""ReadVaultWorkflow — shared read handler for all parent workflows.

Runs on the vault-default queue. Before reading, executes the
``ensure_synced`` Update on the long-running VaultManagerWorkflow (well-known
ID ``vault-manager``). The Update is dispatched via the
``ensure_vault_synced`` Activity because the Python SDK's
``ExternalWorkflowHandle`` does not expose ``execute_update``; the activity
uses a Temporal Client to call the Update and blocks until it returns.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from apps.vault_worker.activities.vault_io import (
        get_code_registry,
        get_skeleton,
        list_notes_in,
        read_note,
    )
    from apps.vault_worker.activities.vault_manager_client import (
        ensure_vault_synced,
    )
    from packages.shared.models import CodeRegistryEntry, VaultContext
    from packages.shared.workflow_names import VAULT_MANAGER_ID


@dataclass
class ReadVaultInput:
    vault_path: str
    context_code: str


@workflow.defn
class ReadVaultWorkflow:
    @workflow.run
    async def run(self, input: ReadVaultInput) -> VaultContext:
        await workflow.execute_activity(
            ensure_vault_synced,
            args=[VAULT_MANAGER_ID],
            start_to_close_timeout=timedelta(minutes=5),
        )

        skeleton = await workflow.execute_activity(
            get_skeleton,
            args=[input.vault_path],
            schedule_to_close_timeout=timedelta(minutes=1),
        )

        registry_entries: list[CodeRegistryEntry] = await workflow.execute_activity(
            get_code_registry,
            args=[input.vault_path],
            schedule_to_close_timeout=timedelta(minutes=1),
        )

        entry = next(
            (e for e in registry_entries if e.code == input.context_code),
            None,
        )
        if entry is None:
            raise ValueError(
                f"context_code {input.context_code!r} not found in code registry"
            )

        folder = entry.folder
        root_note_path = f"{folder}/{entry.name}.md"

        root_note = await workflow.execute_activity(
            read_note,
            args=[input.vault_path, root_note_path],
            schedule_to_close_timeout=timedelta(minutes=1),
        )
        if root_note is None:
            raise ValueError(f"root note not found: {root_note_path}")

        note_paths: list[str] = await workflow.execute_activity(
            list_notes_in,
            args=[input.vault_path, folder],
            schedule_to_close_timeout=timedelta(minutes=1),
        )

        related_notes = []
        for path in note_paths:
            if path == root_note_path:
                continue
            note = await workflow.execute_activity(
                read_note,
                args=[input.vault_path, path],
                schedule_to_close_timeout=timedelta(minutes=1),
            )
            if note is not None:
                related_notes.append(note)

        code_registry = "\n".join(
            f"{e.code}: {e.name} ({e.type}) - {e.folder}" for e in registry_entries
        )

        return VaultContext(
            context_code=input.context_code,
            root_note=root_note,
            related_notes=related_notes,
            skeleton=skeleton,
            code_registry=code_registry,
        )
