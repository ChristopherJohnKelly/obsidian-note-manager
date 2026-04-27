"""NightWatchmanWorkflow — end-to-end audit pipeline.

sync → scan → sort → slice[:10] → generate_fix loop → WriteVault → create_github_pr
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from apps.vault_worker.activities.vault_io import scan_vault, read_note
    from apps.vault_worker.activities.llm import generate_fix, LLM_RETRY_POLICY
    from apps.vault_worker.activities.github_ops import create_github_pr, CreatePRInput
    from apps.vault_worker.workflows.read_vault import ReadVaultInput, ReadVaultWorkflow
    from apps.vault_worker.workflows.write_vault import (
        WriteVaultWorkflow,
        WriteVaultInput,
        WriteOperation,
    )
    from packages.shared.models import AuditProposal, VaultNote, Frontmatter
    from packages.shared.workflow_names import QUEUE_DEFAULT, QUEUE_MUTATION


@dataclass
class NightWatchmanInput:
    vault_path: str
    context_code: str
    repo_owner: str
    repo_name: str
    github_token: str
    pr_branch: str
    base_branch: str = "main"


QRY_GET_PROGRESS = "get_progress"


@workflow.defn
class NightWatchmanWorkflow:
    def __init__(self) -> None:
        self._files_scanned: int = 0
        self._proposals_generated: int = 0

    @workflow.query(name=QRY_GET_PROGRESS)
    def get_progress(self) -> dict[str, int]:
        return {"files_scanned": self._files_scanned, "proposals_generated": self._proposals_generated}

    @workflow.run
    async def run(self, input: NightWatchmanInput) -> dict[str, object]:
        # Step 1: sync vault via child ReadVaultWorkflow
        vault_ctx = await workflow.execute_child_workflow(
            ReadVaultWorkflow.run,
            ReadVaultInput(vault_path=input.vault_path, context_code=input.context_code),
            task_queue=QUEUE_DEFAULT,
            id=f"nw-read-{workflow.info().workflow_id}",
        )

        # Step 2: scan vault
        results = await workflow.execute_activity(
            scan_vault,
            args=[input.vault_path],
            schedule_to_close_timeout=timedelta(minutes=5),
        )

        # Step 3: sort then slice (must happen before loop)
        top = sorted(results, key=lambda r: r.score, reverse=True)[:10]

        # Step 4: generate fixes
        proposals: list[AuditProposal] = []
        for vr in top:
            self._files_scanned += 1
            note = await workflow.execute_activity(
                read_note,
                args=[input.vault_path, str(vr.path)],
                schedule_to_close_timeout=timedelta(minutes=2),
            )
            try:
                fix_str = await workflow.execute_activity(
                    generate_fix,
                    args=[note, vr.reasons, vault_ctx],
                    schedule_to_close_timeout=timedelta(minutes=2),
                    retry_policy=LLM_RETRY_POLICY,
                )
            except (ActivityError, ApplicationError) as e:
                workflow.logger.warning("generate_fix failed for %s: %s", vr.path, e)
                continue
            self._proposals_generated += 1
            proposals.append(
                AuditProposal(
                    target_path=vr.path,
                    proposed_content=fix_str,
                    reasons=vr.reasons,
                    score=vr.score,
                )
            )

        # Step 5: build write operations (raw fix text stored verbatim as body)
        operations = [
            WriteOperation(
                op="save",
                path=str(p.target_path),
                note=VaultNote(
                    path=p.target_path,
                    frontmatter=Frontmatter(),
                    body=p.proposed_content,
                ),
            )
            for p in proposals
        ]

        # Step 6: write vault via child WriteVaultWorkflow
        await workflow.execute_child_workflow(
            WriteVaultWorkflow.run,
            WriteVaultInput(
                vault_path=input.vault_path,
                operations=operations,
                commit_message=f"Night Watchman: fix {len(proposals)} notes",
            ),
            task_queue=QUEUE_MUTATION,
            id=f"nw-write-{workflow.info().workflow_id}",
        )

        # Step 7: create GitHub PR
        pr_url = await workflow.execute_activity(
            create_github_pr,
            args=[
                CreatePRInput(
                    repo_owner=input.repo_owner,
                    repo_name=input.repo_name,
                    token=input.github_token,
                    pr_branch=input.pr_branch,
                    title="Night Watchman audit",
                    body=f"Automated audit fixed {len(proposals)} notes",
                    base_branch=input.base_branch,
                )
            ],
            schedule_to_close_timeout=timedelta(minutes=2),
        )

        return {"proposals_generated": len(proposals), "pr_url": pr_url}
