"""VaultManagerWorkflow — long-running coordinator for vault sync state.

Started automatically when the vault-worker starts. Validates the vault,
stays alive indefinitely, handles ensure_synced Updates from ReadVaultWorkflow,
and calls continue_as_new periodically to prevent history bloat.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from temporalio import workflow
from temporalio.exceptions import ApplicationError
from packages.shared.workflow_names import VAULT_MANAGER_WORKFLOW, UPD_ENSURE_SYNCED


@dataclass
class VaultManagerInput:
    vault_path: str
    repo_url: str
    pat: str
    last_synced: str | None = None  # ISO UTC string; None = first run


@workflow.defn(name=VAULT_MANAGER_WORKFLOW)
class VaultManagerWorkflow:
    def __init__(self) -> None:
        self._last_synced: datetime | None = None
        self._status: str = "initialising"
        self._update_count: int = 0
        self._input: VaultManagerInput | None = None
        # Python SDK update handlers are coroutines and can interleave at await
        # points; serialise the stale-check + pull with a Lock so that two
        # concurrent Updates don't both observe "stale" and fire duplicate pulls.
        self._sync_lock = asyncio.Lock()

    @workflow.update(name=UPD_ENSURE_SYNCED)
    async def ensure_synced(self) -> None:
        """Called by ReadVaultWorkflow before reading. Pulls if stale (> 5 min)."""
        self._update_count += 1
        if self._status != "ready":
            raise ApplicationError("Vault not yet initialised", non_retryable=True)

        async with self._sync_lock:
            now = workflow.now()  # UTC-aware — always use this, never datetime.now()
            stale = self._last_synced is None or (now - self._last_synced) > timedelta(minutes=5)
            if stale:
                await workflow.execute_activity(
                    "git_pull",
                    args=[self._input.vault_path],
                    schedule_to_close_timeout=timedelta(minutes=5),
                )
                self._last_synced = workflow.now()

    @workflow.query
    def get_sync_status(self) -> dict:
        return {
            "status": self._status,
            "last_synced": self._last_synced.isoformat() if self._last_synced else None,
        }

    @workflow.run
    async def run(self, input: VaultManagerInput) -> None:
        self._input = input

        if input.last_synced is not None:
            # Resuming after continue_as_new — restore last_synced from input.
            # The string was produced by workflow.now().isoformat(), so it is always
            # UTC-aware (contains "+00:00"). fromisoformat() parses it correctly.
            # Guard with replace(tzinfo=timezone.utc) in case of any legacy naive strings.
            dt = datetime.fromisoformat(input.last_synced)
            self._last_synced = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            self._status = "ready"
        else:
            # First run — initialise vault
            state = await workflow.execute_activity(
                "check_vault_dir_state",
                args=[input.vault_path],
                schedule_to_close_timeout=timedelta(minutes=1),
            )
            if state == "empty":
                await workflow.execute_activity(
                    "git_clone",
                    args=[input.repo_url, input.vault_path, input.pat],
                    schedule_to_close_timeout=timedelta(minutes=10),
                )
            elif state == "valid_repo":
                await workflow.execute_activity(
                    "git_pull",
                    args=[input.vault_path],
                    schedule_to_close_timeout=timedelta(minutes=5),
                )
            else:
                raise ApplicationError(
                    f"VAULT_PATH '{input.vault_path}' is non-empty and not a git repo. "
                    "Remove or correct VAULT_PATH before starting the worker.",
                    non_retryable=True,
                )
            self._last_synced = workflow.now()
            self._status = "ready"

        # Running phase: handle ensure_synced Updates indefinitely.
        # continue_as_new daily (or after 1,000 updates) to prevent history bloat.
        # wait_condition raises asyncio.TimeoutError on timeout — that is the
        # normal path to continue_as_new, not a failure.
        try:
            await workflow.wait_condition(
                lambda: self._update_count >= 1000,
                timeout=timedelta(days=1),
            )
        except asyncio.TimeoutError:
            pass
        workflow.continue_as_new(VaultManagerInput(
            vault_path=input.vault_path,
            repo_url=input.repo_url,
            pat=input.pat,
            last_synced=self._last_synced.isoformat() if self._last_synced else None,
        ))