from temporalio.client import Client

from packages.shared.models import ChatMessage, FilingProposal
from packages.shared.workflow_names import (
    COPILOT_SESSION_WORKFLOW,
    QUEUE_DEFAULT,
    QRY_GET_DRAFT_PROPOSAL,
    QRY_GET_HISTORY,
    QRY_GET_STATUS,
)


class CopilotTemporalClient:
    def __init__(self, client: Client) -> None:
        self.client = client

    async def start_copilot_session(self, session_id: str, vault_path: str) -> str:
        wf_id = f"copilot-session-{session_id}"
        await self.client.start_workflow(
            COPILOT_SESSION_WORKFLOW,
            args=[{"vault_path": vault_path}],
            id=wf_id,
            task_queue=QUEUE_DEFAULT,
        )
        return wf_id

    async def send_user_message(self, workflow_id: str, message: str) -> None:
        handle = self.client.get_workflow_handle(workflow_id)
        await handle.signal("SIG_RECEIVE_MESSAGE", {"role": "user", "content": message})

    async def get_chat_history(self, workflow_id: str) -> list[ChatMessage]:
        handle = self.client.get_workflow_handle(workflow_id)
        raw = await handle.query(QRY_GET_HISTORY)
        return [ChatMessage(**d) for d in raw]

    async def list_pending_filer_proposals(self) -> list[tuple[str, FilingProposal]]:
        out: list[tuple[str, FilingProposal]] = []
        q = "WorkflowType = 'FilerIngestionWorkflow' AND ExecutionStatus = 'Running'"
        async for ex in self.client.list_workflows(q):
            h = self.client.get_workflow_handle(ex.id)
            status = await h.query(QRY_GET_STATUS)
            if status != "awaiting_approval":
                continue
            raw = await h.query(QRY_GET_DRAFT_PROPOSAL)
            if raw is None:
                continue
            out.append((ex.id, FilingProposal(**raw)))
        return out
