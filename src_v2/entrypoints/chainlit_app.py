"""Chainlit Copilot entrypoint for synchronous vault co-creation."""

import asyncio

import chainlit as cl
from chainlit.input_widget import Select

from src_v2.config.settings import Settings
from src_v2.entrypoints.chainlit_helpers import scan_top_level_dirs
from src_v2.infrastructure.file_system.adapters import ObsidianFileSystemAdapter
from src_v2.use_cases.chat_service import ChatService


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
        await msg.update()
    except ValueError as e:
        msg.content = str(e)
        await msg.update()
    except Exception as e:
        msg.content = f"Error: {e}"
        await msg.update()
