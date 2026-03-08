"""Chainlit Copilot entrypoint for synchronous vault co-creation."""

import chainlit as cl
from chainlit.input_widget import Select

from src_v2.config.settings import Settings
from src_v2.entrypoints.chainlit_helpers import scan_top_level_dirs


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
    """Stub handler: placeholder until Agent 1 (Bubble 2) is implemented."""
    await cl.Message(
        content="Select a Vault Area and ask a question."
    ).send()
