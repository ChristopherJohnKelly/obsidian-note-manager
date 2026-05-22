import argparse
import asyncio
import os
import sys
from dataclasses import dataclass

from temporalio.client import Client

NIGHT_WATCHMAN_WORKFLOW = "NightWatchmanWorkflow"
FILER_INGESTION_WORKFLOW = "FilerIngestionWorkflow"

QUEUE_DEFAULT = "obsidian-note-manager"

_client = None


def configure_client(client):
    global _client
    _client = client


@dataclass
class NightWatchmanInput:
    vault_path: str
    context_code: str
    repo_owner: str
    repo_name: str
    github_token: str
    pr_branch: str
    base_branch: str = "main"


@dataclass
class FilerIngestionInput:
    vault_path: str
    source_path: str
    context_code: str


WORKFLOWS = {
    NIGHT_WATCHMAN_WORKFLOW: {},
    FILER_INGESTION_WORKFLOW: {},
}


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--source-path", default=None)
    return parser


def _build_input(args):
    if args.workflow == NIGHT_WATCHMAN_WORKFLOW:
        return NightWatchmanInput(
            vault_path=os.environ.get("VAULT_PATH", ""),
            context_code=os.environ.get("CONTEXT_CODE", ""),
            repo_owner=os.environ.get("REPO_OWNER", ""),
            repo_name=os.environ.get("REPO_NAME", ""),
            github_token=os.environ.get("GITHUB_TOKEN", ""),
            pr_branch=os.environ.get("PR_BRANCH", ""),
        )
    return FilerIngestionInput(
        vault_path=os.environ.get("VAULT_PATH", ""),
        source_path=args.source_path or "",
        context_code=os.environ.get("CONTEXT_CODE", ""),
    )


async def amain(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.workflow not in WORKFLOWS:
        print(f"Unknown workflow: {args.workflow}", file=sys.stderr)
        return 1

    client = _client or await Client.connect(os.environ.get("TEMPORAL_HOST", "localhost:7233"))
    input_obj = _build_input(args)

    await client.start_workflow(
        args.workflow,
        input_obj,
        id=f"{args.workflow}-{os.environ.get('RUN_ID', 'default')}",
        task_queue=QUEUE_DEFAULT,
    )
    return 0


def main(argv=None) -> int:
    return asyncio.run(amain(argv))


if __name__ == "__main__":
    sys.exit(main())
