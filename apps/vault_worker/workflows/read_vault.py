"""ReadVaultWorkflow — shared read handler that all parent workflows use to gather vault context.

Runs on the vault-default queue and enforces a pull-if-stale sync policy via an
ensure_synced Update to the long-running VaultManagerWorkflow (well-known ID vault-manager).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

from apps.vault_worker.activities.vault_io import (
    get_code_registry,
    get_skeleton,
    list_notes_in,
    read_note,
)
from packages.shared.models import CodeRegistryEntry, VaultContext
from packages.shared.workflow_names import QUEUE_DEFAULT, UPD_ENSURE_SYNCED, VAULT_MANAGER_ID


@dataclass
class ReadVaultInput:
    vault_path: str
    context_code: str  # e.g., "OBSE-P1" — scopes the related_notes


@workflow.defn
class ReadVaultWorkflow:
    """Workflow that reads vault context for a given project/area.

    Before reading, sends an ensure_synced Update to the VaultManagerWorkflow
    (well‑known ID vault‑manager) and blocks until the Update returns.
    VaultManagerWorkflow owns the last_synced state and decides whether a git_pull
    is needed, preventing concurrent read workflows from triggering simultaneous pulls.
    """

    @workflow.run
    async def run(self, input: ReadVaultInput) -> VaultContext:
        # Delegate sync decision to VaultManagerWorkflow — it owns last_synced state.
        # This blocks until VaultManagerWorkflow confirms the vault is fresh
        # (pulling if stale, no-op if recent). Do not call git_pull directly here.
        mgr = workflow.get_external_workflow_handle(VAULT_MANAGER_ID)
        print(f"ReadVaultWorkflow: sending ensure_synced update to {VAULT_MANAGER_ID}")
        try:
            await mgr.update(UPD_ENSURE_SYNCED)
        except AttributeError as e:
            print(f"AttributeError: {e}, dir(mgr)={dir(mgr)}")
            raise
        print("ReadVaultWorkflow: ensure_synced update completed")

        # Read activities run after sync is confirmed
        skeleton = await workflow.execute_activity(
            get_skeleton,
            args=[input.vault_path],
            schedule_to_close_timeout=timedelta(minutes=1),
        )

        registry_entries = await workflow.execute_activity(
            get_code_registry,
            args=[input.vault_path],
            schedule_to_close_timeout=timedelta(minutes=1),
        )

        # Find entry matching the context_code
        entry: CodeRegistryEntry | None = None
        for e in registry_entries:
            if e.code == input.context_code:
                entry = e
                break
        if entry is None:
            # Fallback to default folder structure (should not happen in tests)
            folder = f"20. Projects/{input.context_code}/"
            root_note_path = f"{folder}{input.context_code} - Project Root.md"
        else:
            folder = entry.folder
            root_note_path = f"{folder}/{entry.name}.md"

        # Read root note
        root_note = await workflow.execute_activity(
            read_note,
            args=[input.vault_path, root_note_path],
            schedule_to_close_timeout=timedelta(minutes=1),
        )
        if root_note is None:
            raise ValueError(f"Root note not found: {root_note_path}")

        # List all notes in the folder
        note_paths = await workflow.execute_activity(
            list_notes_in,
            args=[input.vault_path, folder],
            schedule_to_close_timeout=timedelta(minutes=1),
        )

        # Read each note (excluding root note if already in list)
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

        # Format code registry as string
        code_registry_lines = []
        for e in registry_entries:
            code_registry_lines.append(f"{e.code}: {e.name} ({e.type}) - {e.folder}")
        code_registry = "\n".join(code_registry_lines)

        return VaultContext(
            context_code=input.context_code,
            root_note=root_note,
            related_notes=related_notes,
            skeleton=skeleton,
            code_registry=code_registry,
        )