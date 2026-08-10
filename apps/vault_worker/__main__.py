"""Container entrypoint: connect to Temporal, bootstrap the VaultManager, run both workers.

Composes the pieces worker.py exposes, per their documented intent:
vault_input_from_env() reads VAULT_PATH / REPO_URL / GITHUB_PAT;
start_vault_manager() blocks until the vault sync reports ready;
create_workers() returns the default + mutation workers to run together.
"""
import asyncio
import os

from temporalio.client import Client

from apps.vault_worker.worker import (
    create_workers,
    start_vault_manager,
    vault_input_from_env,
)


async def main() -> None:
    client = await Client.connect(
        os.environ.get("TEMPORAL_HOST", "temporal-server:7233")
    )
    await start_vault_manager(client, vault_input_from_env())
    workers = create_workers(client)
    await asyncio.gather(*(worker.run() for worker in workers))


if __name__ == "__main__":
    asyncio.run(main())
