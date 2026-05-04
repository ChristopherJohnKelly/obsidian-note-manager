"""FilerIngestionWorkflow — inbox note filing orchestrator.

Read inbox note → generate filing proposal → await human approval →
write vault (save to proposed path, delete from inbox).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from apps.vault_worker.activities.vault_io import read_note
    from apps.vault_worker.activities.llm import generate_proposal, LLM_RETRY_POLICY
    from apps.vault_worker.core.response_parser import parse_llm_response
    from apps.vault_worker.workflows.read_vault import ReadVaultInput, ReadVaultWorkflow
    from apps.vault_worker.workflows.write_vault import (
        WriteVaultWorkflow,
        WriteVaultInput,
        WriteOperation,
    )
    from packages.shared.models import FilingProposal, Frontmatter, VaultNote
    from packages.shared.workflow_names import QUEUE_DEFAULT, QUEUE_MUTATION


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
        vault_ctx = await workflow.execute_child_workflow(
            ReadVaultWorkflow.run,
            ReadVaultInput(vault_path=input.vault_path, context_code=input.context_code),
            task_queue=QUEUE_DEFAULT,
            id=f"filer-read-{workflow.info().workflow_id}",
        )

        source_note = await workflow.execute_activity(
            read_note,
            args=[input.vault_path, input.source_path],
            schedule_to_close_timeout=timedelta(minutes=1),
        )
        source_body = source_note.body if source_note else ""

        llm_response = await workflow.execute_activity(
            generate_proposal,
            args=[vault_ctx, source_body],
            schedule_to_close_timeout=timedelta(minutes=5),
            retry_policy=LLM_RETRY_POLICY,
        )

        parsed_files = parse_llm_response(llm_response)
        if not parsed_files:
            raise ValueError("LLM response contained no %%FILE%% blocks")
        parsed = parsed_files[0]

        proposal = FilingProposal(
            source_path=Path(input.source_path),
            proposed_path=Path(parsed["path"]),
            proposed_frontmatter=Frontmatter(),
            reasoning="",
        )
        self._proposal = proposal.model_dump(mode="json")
        self._status = "awaiting_approval"

        await workflow.wait_condition(lambda: self._decision is not None)

        if self._decision == "approve":
            self._status = "filing"
            await workflow.execute_child_workflow(
                WriteVaultWorkflow.run,
                WriteVaultInput(
                    vault_path=input.vault_path,
                    operations=[
                        WriteOperation(
                            op="save",
                            path=str(proposal.proposed_path),
                            note=VaultNote(
                                path=proposal.proposed_path,
                                frontmatter=Frontmatter(),
                                body=parsed["content"],
                            ),
                        ),
                        WriteOperation(
                            op="delete",
                            path=str(proposal.source_path),
                        ),
                    ],
                    commit_message=f"Filer: file {input.source_path} → {parsed['path']}",
                ),
                task_queue=QUEUE_MUTATION,
                id=f"filer-write-{workflow.info().workflow_id}",
            )
            self._status = "complete"
            return "filed"
        elif self._decision == "reject":
            self._status = "rejected"
            return "rejected"
