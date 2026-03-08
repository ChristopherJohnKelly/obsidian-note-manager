"""Chainlit Copilot entrypoint for synchronous vault co-creation."""

import asyncio

import chainlit as cl
from chainlit.input_widget import Select

from src_v2.config.settings import Settings
from src_v2.entrypoints.chainlit_helpers import scan_top_level_dirs
from src_v2.infrastructure.file_system.adapters import ObsidianFileSystemAdapter
from src_v2.use_cases.chat_service import ChatService
from src_v2.use_cases.proposal_service import ProposalService


@cl.on_chat_start
async def start() -> None:
    """Scan vault on chat start and populate Vault Area dropdown in Chat Settings."""
    settings = Settings()
    dirs = scan_top_level_dirs(settings.vault_root)
    if not dirs:
        dirs = ["(No vault folders found)"]

    chat_settings = await cl.ChatSettings(
        [
            Select(
                id="active_area",
                label="Vault Area",
                values=dirs,
                initial_index=0,
            ),
        ]
    ).send()

    cl.user_session.set("active_area", chat_settings["active_area"])


@cl.on_settings_update
async def on_settings_update(settings: dict) -> None:
    """Update session when user changes the Vault Area dropdown."""
    cl.user_session.set("active_area", settings["active_area"])


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Run Agent 1 (The Analyst) to answer questions about the selected vault area."""
    active_area = cl.user_session.get("active_area")
    if not active_area or active_area == "(No vault folders found)":
        await cl.Message(
            content="Please select a valid Vault Area from Settings first."
        ).send()
        return

    settings = Settings()
    repo = ObsidianFileSystemAdapter(settings.vault_root)
    service = ChatService(
        repo,
        vault_root=settings.vault_root,
        api_key=settings.gemini_api_key or None,
    )

    msg = cl.Message(content="")
    await msg.send()

    try:
        response = await asyncio.to_thread(
            service.chat,
            message.content,
            active_area,
        )
        msg.content = response
        msg.actions = [
            cl.Action(
                name="draft_updates",
                payload="draft",
                label="Draft Updates",
                tooltip="Draft file updates to Obsidian Review Queue",
            )
        ]
        await msg.update()
    except ValueError as e:
        msg.content = str(e)
        await msg.update()
    except Exception as e:
        msg.content = f"Error: {e}"
        await msg.update()


@cl.action_callback("draft_updates")
async def on_draft_updates(action: cl.Action) -> None:
    """Trigger Agent 2 (The Proposer) to draft file updates to the Review Queue."""
    await action.remove()

    status_msg = cl.Message(content="Drafting proposal to Obsidian Review Queue...")
    await status_msg.send()

    active_area = cl.user_session.get("active_area")
    if not active_area or active_area == "(No vault folders found)":
        status_msg.content = "Please select a valid Vault Area from Settings first."
        await status_msg.update()
        return

    try:
        history = cl.chat_context.to_openai()
    except Exception:
        history = []

    settings = Settings()
    repo = ObsidianFileSystemAdapter(settings.vault_root)
    service = ProposalService(
        repo,
        vault_root=settings.vault_root,
        review_dir=settings.review_dir,
        api_key=settings.gemini_api_key or None,
    )

    try:
        result = await asyncio.to_thread(
            service.generate_draft,
            history,
            active_area,
        )
        status_msg.content = result
    except Exception as e:
        status_msg.content = f"Error: {e}"

    await status_msg.update()
