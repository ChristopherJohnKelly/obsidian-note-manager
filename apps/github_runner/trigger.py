import argparse
import asyncio
import os
import sys
from dataclasses import dataclass

from temporalio.client import Client

from packages.shared.workflow_names import (
    NIGHT_WATCHMAN_WORKFLOW,
    FILER_INGESTION_WORKFLOW,
    QUEUE_DEFAULT,
)

_client = None


def configure_client(client):
    global _client
    _client = client


WORKFLOWS = {
    NIGHT_WATCHMAN_WORKFLOW: {},
    FILER_INGESTION_WORKFLOW: {},
}


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--source-path", default=None)
    return parser


async def amain(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.workflow not in WORKFLOWS:
        print(f"Unknown workflow: {args.workflow}", file=sys.stderr)
        return 1

    return 0


def main(argv=None) -> int:
    return asyncio.run(amain(argv))


if __name__ == "__main__":
    sys.exit(main())
