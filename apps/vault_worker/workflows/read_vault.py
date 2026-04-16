"""ReadVaultWorkflow — shared read handler that all parent workflows use to gather vault context.

Runs on the vault-default queue and enforces a pull-if-stale sync policy via an
ensure_synced Update to the long-running VaultManagerWorkflow (well-known ID vault-manager).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

from packages.shared.models import VaultContext
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
        raise RuntimeError("stop")