"""FilerIngestionWorkflow — LLM-assisted inbox note filing with HITL approval."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from apps.vault_worker.workflows.read_vault import ReadVaultInput, ReadVaultWorkflow
    from apps.vault_worker.workflows.write_vault import (
        WriteVaultInput,
        WriteVaultWorkflow,
        WriteOperation,
    )
    from apps.vault_worker.activities.llm import generate_proposal, LLM_RETRY_POLICY
    from apps.vault_worker.core.response_parser import parse_llm_response
    from packages.shared.models import FilingProposal, Frontmatter, VaultNote
    from packages.shared.workflow_names import QUEUE_MUTATION


@dataclass
class FilerIngestionInput:
    vault_path: str
    source_path: str
    context_code: str


@workflow.defn
class FilerIngestionWorkflow:
    def __init__(self) -> None:
        self._status: str = "drafting"
        self._proposal: dict | None = None
        self._decision: str | None = None

    @workflow.signal
    async def approve(self) -> None:
        self._decision = "approve"

    @workflow.signal
    async def reject(self) -> None:
        self._decision = "reject"

    @workflow.query
    def get_status(self) -> str:
        return self._status

    @workflow.query
    def get_draft_proposal(self) -> dict | None:
        return self._proposal

    @workflow.run
    async def run(self, input: FilerIngestionInput) -> str:
        # Dispatch ReadVaultWorkflow on the same task queue so tests using a
        # fresh queue (not QUEUE_DEFAULT) can resolve the child workflow.
        vault_ctx = await workflow.execute_child_workflow(
            ReadVaultWorkflow.run,
            ReadVaultInput(vault_path=input.vault_path, context_code=input.context_code),
            task_queue=workflow.info().task_queue,
            id=f"filer-read-{workflow.info().workflow_id}",
        )

        # Status remains "drafting" while the LLM activity runs.
        raw = await workflow.execute_activity(
            generate_proposal,
            args=[vault_ctx, ""],
            schedule_to_close_timeout=timedelta(minutes=2),
            retry_policy=LLM_RETRY_POLICY,
        )

        # parse_llm_response is pure regex — deterministic, safe in workflow.
        parsed = parse_llm_response(raw)
        proposed_path = parsed[0]["path"]
        proposed_body = parsed[0]["content"]
        proposal = FilingProposal(
            source_path=Path(input.source_path),
            proposed_path=Path(proposed_path),
            proposed_frontmatter=Frontmatter(),
            reasoning="",
        )
        self._proposal = proposal.model_dump(mode="json")
        self._status = "awaiting_approval"

        try:
            await workflow.wait_condition(
                lambda: self._decision is not None,
                timeout=timedelta(weeks=1),
            )
        except asyncio.TimeoutError:
            self._status = "expired"
            return "expired"

        if self._decision == "reject":
            self._status = "rejected"
            return "rejected"

        self._status = "filing"
        await workflow.execute_child_workflow(
            WriteVaultWorkflow.run,
            WriteVaultInput(
                vault_path=input.vault_path,
                operations=[
                    WriteOperation(
                        op="save",
                        path=proposed_path,
                        note=VaultNote(
                            path=Path(proposed_path),
                            frontmatter=Frontmatter(),
                            body=proposed_body,
                        ),
                    ),
                    WriteOperation(
                        op="delete",
                        path=input.source_path,
                    ),
                ],
                commit_message=f"File: {input.source_path} → {proposed_path}",
            ),
            task_queue=QUEUE_MUTATION,
            id=f"filer-write-{workflow.info().workflow_id}",
        )

        self._status = "complete"
        return "filed"
