"""Activity shim for calling Updates on VaultManagerWorkflow.

The Temporal Python SDK's ``workflow.get_external_workflow_handle()`` exposes
only ``.signal()`` and ``.cancel()`` — there is no cross-workflow
``execute_update``. The sanctioned workaround for the Update contract in
TRD §4.6 / §7.4 (ReadVaultWorkflow blocks on ``ensure_synced`` Update until
VaultManagerWorkflow confirms the vault is fresh) is to call the Update via
a Temporal ``Client`` from inside an Activity. Activities run outside the
workflow sandbox and can hold a ``Client`` reference.

Tests inject a client via :func:`configure_client`; production wires the
real worker's Temporal Client the same way before Worker start.
"""

from __future__ import annotations

from temporalio import activity
from temporalio.client import Client

from packages.shared.workflow_names import UPD_ENSURE_SYNCED


_client: Client | None = None


def configure_client(client: Client | None) -> None:
    """Inject the Temporal Client used by vault-manager Update activities.

    Call this before registering Activities with the Worker:
    - Production: configure_client(worker_client)
    - Tests: configure_client(pydantic_client) via fixture
    """
    global _client
    _client = client


def _get_client() -> Client:
    if _client is None:
        raise RuntimeError(
            "Temporal Client not configured. "
            "Call configure_client(client) before running vault-manager Activities."
        )
    return _client


@activity.defn
async def ensure_vault_synced(manager_id: str) -> None:
    """Execute the ensure_synced Update on the VaultManagerWorkflow.

    Blocks until the Update handler returns (pull-if-stale on the manager
    side). Any exception from the handler propagates and fails the activity,
    which fails the calling ReadVaultWorkflow.
    """
    client = _get_client()
    handle = client.get_workflow_handle(manager_id)
    await handle.execute_update(UPD_ENSURE_SYNCED)
