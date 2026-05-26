import asyncio
import os
import chainlit as cl
from temporalio.client import Client
from apps.copilot_ui.temporal_client import CopilotTemporalClient


temporal = None


async def _get_client() -> CopilotTemporalClient:
    global temporal
    if temporal is None:
        client = await Client.connect(os.environ["TEMPORAL_ADDRESS"])
        temporal = CopilotTemporalClient(client)
    return temporal


@cl.on_chat_start
async def on_chat_start():
    client = await _get_client()
    wf_id = cl.user_session.get("workflow_id")

    if wf_id:
        handle = client.client.get_workflow_handle(wf_id)
        desc = await handle.describe()
        if desc.status and desc.status.name == "RUNNING":
            history = await client.get_chat_history(wf_id)
            for msg in history:
                await cl.Message(content=msg.content, author=msg.role).send()
            return

    session_id = cl.user_session.get("id")
    vault_path = os.environ.get("VAULT_PATH", "/vault")
    new_wf_id = await client.start_copilot_session(
        session_id=session_id,
        vault_path=vault_path,
    )
    cl.user_session.set("workflow_id", new_wf_id)

    proposals = await client.list_pending_filer_proposals()
    for proposal_wf_id, proposal in proposals:
        actions = [
            cl.Action(name="approve", payload={"workflow_id": proposal_wf_id}, label="Approve"),
            cl.Action(name="reject", payload={"workflow_id": proposal_wf_id}, label="Reject"),
        ]
        await cl.Message(
            content=f"Proposal: {proposal.source_path} → {proposal.proposed_path}\n{proposal.reasoning}",
            actions=actions,
        ).send()


@cl.on_message
async def on_message(message: cl.Message):
    client = await _get_client()
    wf_id = cl.user_session.get("workflow_id")

    await client.send_user_message(wf_id, message.content)

    prev_history = await client.get_chat_history(wf_id)
    prev_len = len(prev_history)

    while True:
        history = await client.get_chat_history(wf_id)
        if len(history) > prev_len and history[-1].role == "assistant":
            await cl.Message(content=history[-1].content).send()
            break
        await asyncio.sleep(0.5)


@cl.action_callback("approve")
async def on_approve(action: cl.Action):
    client = await _get_client()
    workflow_id = action.payload["workflow_id"]
    await client.send_filer_decision(workflow_id, approved=True)
    await cl.Message(content="Approved!").send()


@cl.action_callback("reject")
async def on_reject(action: cl.Action):
    client = await _get_client()
    workflow_id = action.payload["workflow_id"]
    await client.send_filer_decision(workflow_id, approved=False)
    await cl.Message(content="Rejected.").send()
