from temporalio.client import Client

from packages.shared.workflow_names import COPILOT_SESSION_WORKFLOW, QUEUE_DEFAULT


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
