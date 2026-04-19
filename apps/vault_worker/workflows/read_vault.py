"""ReadVaultWorkflow — shared read handler for all parent workflows.

Runs on the vault-default queue. Emulates Update semantics against the
long-running VaultManagerWorkflow (well-known ID ``vault-manager``) via a
request-Signal + reply-Signal pair: we signal SIG_ENSURE_SYNCED with our
own workflow ID as the reply address, then block on wait_condition until
VaultManager signals SIG_SYNC_ACK back. The SDK's ExternalWorkflowHandle
does not expose execute_update, so Signal-with-reply is the correct
workflow-to-workflow coordination primitive here.
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
    from packages.shared.models import CodeRegistryEntry, VaultContext
    from packages.shared.workflow_names import (
        SIG_ENSURE_SYNCED,
        SIG_SYNC_ACK,
        VAULT_MANAGER_ID,
    )


@dataclass
class ReadVaultInput:
    vault_path: str
    context_code: str


@workflow.defn
class ReadVaultWorkflow:
    _SYNC_TIMEOUT = timedelta(minutes=5)

    def __init__(self) -> None:
        self._synced: bool = False

    @workflow.signal(name=SIG_SYNC_ACK)
    async def on_sync_ack(self) -> None:
        self._synced = True

    @workflow.run
    async def run(self, input: ReadVaultInput) -> VaultContext:
        mgr = workflow.get_external_workflow_handle(VAULT_MANAGER_ID)
        await mgr.signal(SIG_ENSURE_SYNCED, workflow.info().workflow_id)

        await workflow.wait_condition(
            lambda: self._synced,
            timeout=self._SYNC_TIMEOUT,
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
